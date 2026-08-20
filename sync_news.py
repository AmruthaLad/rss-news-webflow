import os
import re
import requests
import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


# ============================================================
# CONFIGURATION
# ============================================================

WEBFLOW_API_TOKEN = os.environ["WEBFLOW_API_TOKEN"]
RSS_FEED_URL = os.environ["RSS_FEED_URL"]

# Ticker collection
TICKER_COLLECTION_ID = os.environ["WEBFLOW_COLLECTION_ID"]

# Trending News collection
TRENDING_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"

# Webflow site
WEBFLOW_SITE_ID = os.environ["WEBFLOW_SITE_ID"]

# Number of RSS articles to process
MAX_ARTICLES = 10

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================
# CREATE SLUG
# ============================================================

def make_slug(title):

    slug = str(title).lower().strip()

    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)

    return slug.strip("-")[:250]


# ============================================================
# PARSE RSS DATE
# ============================================================

def parse_date(date_string):

    if not date_string:
        return None

    try:

        dt = parsedate_to_datetime(date_string)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone(timezone.utc)

        return dt.isoformat().replace("+00:00", "Z")

    except Exception as error:

        print(f"Date parsing error: {error}")

        return None


# ============================================================
# READ RSS FEED
# ============================================================

def read_rss():

    print("Reading RSS feed...")

    feed = feedparser.parse(RSS_FEED_URL)

    articles = []

    for entry in feed.entries:

        title = entry.get("title", "").strip()

        url = (
            entry.get("link")
            or entry.get("url")
            or ""
        ).strip()

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        source = ""

        if entry.get("source"):

            source_data = entry.get("source")

            if isinstance(source_data, dict):

                source = (
                    source_data.get("title")
                    or ""
                ).strip()

        if not source:

            source = (
                entry.get("author")
                or ""
            ).strip()

        if not source:

            source = "Unknown"

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        rss_date = (
            entry.get("published")
            or entry.get("updated")
            or ""
        ).strip()

        publish_date = parse_date(rss_date)

        # ----------------------------------------------------
        # IMAGE
        #
        # Intentionally NOT sent to Webflow.
        # ----------------------------------------------------

        image_url = ""

        if entry.get("media_content"):

            try:

                image_url = (
                    entry.media_content[0]
                    .get("url", "")
                )

            except Exception:
                image_url = ""

        if not image_url and entry.get("media_thumbnail"):

            try:

                image_url = (
                    entry.media_thumbnail[0]
                    .get("url", "")
                )

            except Exception:
                image_url = ""

        # ----------------------------------------------------
        # VALID ARTICLE
        # ----------------------------------------------------

        if not title or not url:
            continue

        articles.append({
            "title": title,
            "url": url,
            "source": source,
            "date": rss_date,
            "publish_date": publish_date,
            "image": image_url
        })

    print(f"Found {len(articles)} RSS articles")

    return articles


# ============================================================
# GET LATEST ARTICLES
# ============================================================

def get_latest_articles(articles):

    def date_value(article):

        try:

            if article["publish_date"]:

                return datetime.fromisoformat(
                    article["publish_date"]
                    .replace("Z", "+00:00")
                )

        except Exception:
            pass

        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    articles.sort(
        key=date_value,
        reverse=True
    )

    selected = articles[:MAX_ARTICLES]

    print(
        f"Processing latest {len(selected)} articles..."
    )

    return selected


# ============================================================
# GET ALL WEBFLOW ITEMS
# ============================================================

def get_collection_items(collection_id):

    print("Reading existing Webflow items...")

    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items"
    )

    all_items = []

    offset = 0

    while True:

        params = {
            "offset": offset,
            "limit": 100
        }

        response = requests.get(
            url,
            headers=HEADERS,
            params=params
        )

        if response.status_code != 200:

            print(
                "Webflow API error while reading "
                f"collection: {response.status_code}"
            )

            print(response.text)

            break

        data = response.json()

        items = data.get("items", [])

        all_items.extend(items)

        if len(items) < 100:
            break

        offset += 100

    print(
        f"Found {len(all_items)} existing items."
    )

    return all_items


# ============================================================
# FIND EXISTING ARTICLE
# ============================================================

def find_existing_item(
    existing_items,
    article_url,
    collection_type
):

    for item in existing_items:

        field_data = item.get(
            "fieldData",
            {}
        )

        if collection_type == "ticker":

            existing_url = field_data.get(
                "news-url"
            )

        else:

            existing_url = field_data.get(
                "news-link"
            )

        if existing_url == article_url:

            return item

    return None


# ============================================================
# BUILD TICKER FIELD DATA
# ============================================================

def build_ticker_fields(article, existing_item=None):

    title = article["title"]
    url = article["url"]
    source = article["source"]
    publish_date = article["publish_date"]

    field_data = {
        "name": title,
        "news-url": url,
        "source": source,
        "slug": make_slug(title)
    }

    if publish_date:

        field_data["publish-date"] = publish_date

    # --------------------------------------------------------
    # If item already exists, preserve its existing slug.
    #
    # This avoids Webflow duplicate slug errors.
    # --------------------------------------------------------

    if existing_item:

        existing_fields = existing_item.get(
            "fieldData",
            {}
        )

        existing_slug = existing_fields.get(
            "slug"
        )

        if existing_slug:

            field_data["slug"] = existing_slug

    return field_data


# ============================================================
# BUILD TRENDING NEWS FIELD DATA
# ============================================================

def build_trending_fields(
    article,
    existing_item=None
):

    title = article["title"]
    url = article["url"]
    source = article["source"]
    publish_date = article["publish_date"]

    field_data = {
        "name": title,
        "news-link": url,
        "source-name": source,
        "slug": make_slug(title)
    }

    if publish_date:

        field_data["publish-date"] = publish_date

    # --------------------------------------------------------
    # NEWS IMAGE IS INTENTIONALLY DISABLED
    #
    # Do NOT add news-image here.
    #
    # The Webflow field exists, but we are not sending it.
    # --------------------------------------------------------

    if existing_item:

        existing_fields = existing_item.get(
            "fieldData",
            {}
        )

        existing_slug = existing_fields.get(
            "slug"
        )

        if existing_slug:

            field_data["slug"] = existing_slug

    return field_data


# ============================================================
# CREATE WEBFLOW ITEM
# ============================================================

def create_item(
    collection_id,
    field_data
):

    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items"
    )

    payload = {
        "fieldData": field_data
    }

    response = requests.post(
        url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in (200, 201):

        print(
            f"Created Webflow item: "
            f"{response.status_code}"
        )

        return True

    print(
        f"Webflow API error: "
        f"{response.status_code}"
    )

    print(response.text)

    return False


# ============================================================
# UPDATE WEBFLOW ITEM
# ============================================================

def update_item(
    collection_id,
    item_id,
    field_data
):

    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items/{item_id}"
    )

    payload = {
        "fieldData": field_data
    }

    response = requests.patch(
        url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in (200, 201):

        print(
            f"Updated Webflow item: "
            f"{response.status_code}"
        )

        return True

    print(
        f"Webflow API error: "
        f"{response.status_code}"
    )

    print(response.text)

    return False


# ============================================================
# SYNC ONE COLLECTION
# ============================================================

def sync_collection(
    collection_id,
    articles,
    collection_type,
    collection_name
):

    print()
    print("======================================")
    print(
        f"SYNCING {collection_name.upper()}"
    )
    print("======================================")

    print(
        f"Collection ID: {collection_id}"
    )

    existing_items = get_collection_items(
        collection_id
    )

    created = 0
    updated = 0
    failed = 0

    for article in articles:

        print()
        print("--------------------------------------")

        print(
            f"Title: {article['title']}"
        )

        print(
            f"Source: {article['source']}"
        )

        print(
            f"Date: {article['date']}"
        )

        print(
            f"URL: {article['url']}"
        )

        print("--------------------------------------")

        # ----------------------------------------------------
        # FIND EXISTING ARTICLE
        # ----------------------------------------------------

        existing_item = find_existing_item(
            existing_items,
            article["url"],
            collection_type
        )

        # ----------------------------------------------------
        # BUILD FIELD DATA
        # ----------------------------------------------------

        if collection_type == "ticker":

            field_data = build_ticker_fields(
                article,
                existing_item
            )

        else:

            field_data = build_trending_fields(
                article,
                existing_item
            )

        # ----------------------------------------------------
        # UPDATE EXISTING
        # ----------------------------------------------------

        if existing_item:

            item_id = existing_item.get("id")

            print(
                "Existing article found."
            )

            print(
                f"Updating item ID: {item_id}"
            )

            success = update_item(
                collection_id,
                item_id,
                field_data
            )

            if success:

                updated += 1

            else:

                failed += 1

        # ----------------------------------------------------
        # CREATE NEW
        # ----------------------------------------------------

        else:

            print(
                "New article found."
            )

            success = create_item(
                collection_id,
                field_data
            )

            if success:

                created += 1

            else:

                failed += 1

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    print()
    print(
        f"{collection_name.upper()} results:"
    )

    print(
        f"Created: {created}"
    )

    print(
        f"Updated: {updated}"
    )

    print(
        f"Failed: {failed}"
    )

    return {
        "created": created,
        "updated": updated,
        "failed": failed
    }


# ============================================================
# PUBLISH WEBFLOW
# ============================================================

def publish_webflow_site():

    print()
    print("======================================")
    print("PUBLISHING WEBFLOW SITE")
    print("======================================")

    url = (
        f"{WEBFLOW_API_BASE}/sites/"
        f"{WEBFLOW_SITE_ID}/publish"
    )

    payload = {
        "publishToWebflowSubdomain": True
    }

    response = requests.post(
        url,
        headers=HEADERS,
        json=payload
    )

    print(
        f"Webflow publish response: "
        f"{response.status_code}"
    )

    if response.status_code not in (
        200,
        201,
        202
    ):

        print(response.text)

        return False

    print(
        "Webflow site publish request completed."
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("======================================")
    print("STARTING RSS → WEBFLOW SYNC")
    print("======================================")

    print(
        f"Ticker Collection: "
        f"{TICKER_COLLECTION_ID}"
    )

    print(
        f"Trending News Collection: "
        f"{TRENDING_COLLECTION_ID}"
    )

    print(
        f"Site ID: "
        f"{WEBFLOW_SITE_ID}"
    )

    print()

    # --------------------------------------------------------
    # RSS
    # --------------------------------------------------------

    articles = read_rss()

    if not articles:

        print("No RSS articles found.")

        return

    # --------------------------------------------------------
    # LATEST 10
    # --------------------------------------------------------

    articles = get_latest_articles(
        articles
    )

    if not articles:

        print("No articles selected.")

        return

    # --------------------------------------------------------
    # TICKER
    # --------------------------------------------------------

    sync_collection(
        TICKER_COLLECTION_ID,
        articles,
        "ticker",
        "Ticker"
    )

    # --------------------------------------------------------
    # TRENDING NEWS
    # --------------------------------------------------------

    sync_collection(
        TRENDING_COLLECTION_ID,
        articles,
        "trending",
        "Trending News"
    )

    # --------------------------------------------------------
    # PUBLISH
    # --------------------------------------------------------

    publish_webflow_site()

    print()
    print("======================================")
    print("RSS → WEBFLOW SYNC FINISHED")
    print("======================================")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
