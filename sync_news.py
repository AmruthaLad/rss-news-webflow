import os
import re
import requests
import feedparser
from datetime import datetime, timezone
from collections import defaultdict
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

WEBFLOW_SITE_ID = os.environ["WEBFLOW_SITE_ID"]

MAX_TOTAL_ARTICLES = 10
MAX_PER_SOURCE = 2

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def make_slug(title):
    """
    Create Webflow-safe slug.
    """
    slug = clean_text(title).lower()

    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)

    slug = slug.strip("-")

    return slug[:250]


def parse_date(date_string):
    """
    Convert RSS date into ISO 8601 format accepted by Webflow.
    """

    if not date_string:
        return None

    try:
        dt = parsedate_to_datetime(date_string)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone(timezone.utc)

        return dt.isoformat().replace("+00:00", "Z")

    except Exception:
        print(f"Could not parse date: {date_string}")
        return None


# ============================================================
# READ RSS
# ============================================================

def read_rss():

    print("Reading RSS feed...")

    feed = feedparser.parse(RSS_FEED_URL)

    articles = []

    for entry in feed.entries:

        title = clean_text(entry.get("title"))

        url = clean_text(
            entry.get("link")
            or entry.get("url")
        )

        source = clean_text(
            entry.get("source", {}).get("title")
            if isinstance(entry.get("source"), dict)
            else entry.get("author")
        )

        # Fallback source
        if not source:
            source = "Unknown"

        rss_date = clean_text(
            entry.get("published")
            or entry.get("updated")
        )

        image_url = ""

        # ----------------------------------------------------
        # IMAGE EXTRACTION
        # Currently not being sent to Webflow.
        # ----------------------------------------------------

        if entry.get("media_content"):
            try:
                image_url = entry.media_content[0].get("url", "")
            except Exception:
                pass

        if not image_url and entry.get("media_thumbnail"):
            try:
                image_url = entry.media_thumbnail[0].get("url", "")
            except Exception:
                pass

        if not title or not url:
            continue

        articles.append({
            "title": title,
            "url": url,
            "source": source,
            "date": rss_date,
            "publish_date": parse_date(rss_date),
            "image": image_url
        })

    print(f"Found {len(articles)} RSS articles")

    return articles


# ============================================================
# FILTER ARTICLES
# MAXIMUM 2 FROM EACH SOURCE
# MAXIMUM 10 TOTAL
# ============================================================

def select_articles(articles):

    print()
    print("======================================")
    print("FILTERING RSS ARTICLES")
    print("======================================")

    # Sort newest first
    def sort_key(article):
        try:
            if article["publish_date"]:
                return datetime.fromisoformat(
                    article["publish_date"].replace("Z", "+00:00")
                )
        except Exception:
            pass

        return datetime.min.replace(tzinfo=timezone.utc)

    articles.sort(
        key=sort_key,
        reverse=True
    )

    selected_articles = []

    source_counts = defaultdict(int)

    for article in articles:

        source_key = article["source"].strip().lower()

        # Maximum 2 articles from the same source
        if source_counts[source_key] >= MAX_PER_SOURCE:
            continue

        selected_articles.append(article)

        source_counts[source_key] += 1

        # Stop when we have 10 articles
        if len(selected_articles) >= MAX_TOTAL_ARTICLES:
            break

    print(
        f"Selected {len(selected_articles)} articles "
        f"(maximum {MAX_PER_SOURCE} per source)"
    )

    print()

    for source, count in source_counts.items():
        print(f"{source}: {count}")

    print()

    return selected_articles


# ============================================================
# GET COLLECTION ITEMS
# ============================================================

def get_collection_items(collection_id):

    print("Reading existing Webflow items...")

    url = f"{WEBFLOW_API_BASE}/collections/{collection_id}/items"

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
                f"Webflow API error while reading collection: "
                f"{response.status_code}"
            )

            print(response.text)

            return all_items

        data = response.json()

        items = data.get("items", [])

        all_items.extend(items)

        if len(items) < 100:
            break

        offset += 100

    print(f"Found {len(all_items)} existing items.")

    return all_items


# ============================================================
# FIND EXISTING ITEM
# ============================================================

def find_existing_item(items, article_url):

    for item in items:

        field_data = item.get("fieldData", {})

        # -----------------------------------------------
        # Ticker uses news-url
        # Trending uses news-link
        # -----------------------------------------------

        existing_url = (
            field_data.get("news-url")
            or field_data.get("news-link")
        )

        if existing_url == article_url:
            return item

    return None


# ============================================================
# CREATE FIELD DATA
# ============================================================

def build_field_data(article, collection_type):

    title = article["title"]
    url = article["url"]
    source = article["source"]
    publish_date = article["publish_date"]

    slug = make_slug(title)

    # ----------------------------------------------------
    # TICKER COLLECTION
    #
    # Fields:
    # Name
    # News URL
    # Source
    # Publish Date
    # Slug
    # ----------------------------------------------------

    if collection_type == "ticker":

        field_data = {
            "name": title,
            "news-url": url,
            "source": source,
            "slug": slug
        }

        if publish_date:
            field_data["publish-date"] = publish_date

        return field_data

    # ----------------------------------------------------
    # TRENDING NEWS COLLECTION
    #
    # Fields:
    # Name
    # News Link
    # Source Name
    # Publish Date
    # Slug
    #
    # IMAGE INTENTIONALLY COMMENTED OUT
    # ----------------------------------------------------

    if collection_type == "trending":

        field_data = {
            "name": title,
            "news-link": url,
            "source-name": source,
            "slug": slug
        }

        if publish_date:
            field_data["publish-date"] = publish_date

        # ------------------------------------------------
        # NEWS IMAGE TEMPORARILY DISABLED
        #
        # field_data["news-image"] = {
        #     "url": article["image"],
        #     "alt": title
        # }
        # ------------------------------------------------

        return field_data

    return {}


# ============================================================
# CREATE WEBFLOW ITEM
# ============================================================

def create_item(collection_id, article, collection_type):

    url = f"{WEBFLOW_API_BASE}/collections/{collection_id}/items"

    field_data = build_field_data(
        article,
        collection_type
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
        f"Webflow API error: {response.status_code}"
    )

    print(response.text)

    return False


# ============================================================
# UPDATE WEBFLOW ITEM
# ============================================================

def update_item(
    collection_id,
    item_id,
    article,
    collection_type,
    existing_item=None
):

    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items/{item_id}"
    )

    field_data = build_field_data(
        article,
        collection_type
    )

    # ----------------------------------------------------
    # IMPORTANT:
    #
    # Webflow can reject slug updates if another item
    # already owns the slug.
    #
    # For an existing article, we therefore keep the
    # existing item's slug.
    # ----------------------------------------------------

    if existing_item:

        existing_field_data = existing_item.get(
            "fieldData",
            {}
        )

        existing_slug = existing_field_data.get("slug")

        if existing_slug:
            field_data["slug"] = existing_slug

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
        f"Webflow API error: {response.status_code}"
    )

    print(response.text)

    return False


# ============================================================
# SYNC COLLECTION
# ============================================================

def sync_collection(
    collection_id,
    articles,
    collection_type,
    collection_name
):

    print()
    print("======================================")
    print(f"SYNCING {collection_name.upper()}")
    print("======================================")

    print(f"Collection ID: {collection_id}")

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

        existing_item = find_existing_item(
            existing_items,
            article["url"]
        )

        # ==================================================
        # UPDATE EXISTING
        # ==================================================

        if existing_item:

            item_id = existing_item.get("id")

            print("Existing article found.")

            print(
                f"Updating item ID: {item_id}"
            )

            success = update_item(
                collection_id,
                item_id,
                article,
                collection_type,
                existing_item
            )

            if success:
                updated += 1
            else:
                failed += 1

        # ==================================================
        # CREATE NEW
        # ==================================================

        else:

            print("New article found.")

            success = create_item(
                collection_id,
                article,
                collection_type
            )

            if success:
                created += 1
            else:
                failed += 1

    print()
    print(
        f"{collection_name.upper()} results:"
    )

    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")

    return {
        "created": created,
        "updated": updated,
        "failed": failed
    }


# ============================================================
# PUBLISH WEBFLOW SITE
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

    if response.status_code not in (200, 201, 202):

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
    # READ RSS
    # --------------------------------------------------------

    articles = read_rss()

    if not articles:

        print("No RSS articles found.")

        return

    # --------------------------------------------------------
    # FILTER
    # MAX 2 PER SOURCE
    # MAX 10 TOTAL
    # --------------------------------------------------------

    articles = select_articles(
        articles
    )

    if not articles:

        print("No articles selected.")

        return

    print(
        f"Processing latest "
        f"{len(articles)} articles..."
    )

    # --------------------------------------------------------
    # SYNC TICKER
    # --------------------------------------------------------

    ticker_results = sync_collection(
        TICKER_COLLECTION_ID,
        articles,
        "ticker",
        "Ticker"
    )

    # --------------------------------------------------------
    # SYNC TRENDING NEWS
    # --------------------------------------------------------

    trending_results = sync_collection(
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


if __name__ == "__main__":
    main()
