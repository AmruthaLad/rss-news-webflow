import requests
import feedparser
import re
from datetime import datetime
from email.utils import parsedate_to_datetime


# ============================================================
# CONFIGURATION
# ============================================================

WEBFLOW_API_TOKEN = "YOUR_WEBFLOW_API_TOKEN"

SITE_ID = "YOUR_SITE_ID"

RSS_URL = "YOUR_RSS_FEED_URL"

# Your existing Ticker collection ID
TICKER_COLLECTION_ID = "YOUR_TICKER_COLLECTION_ID"

# Trending News collection
TRENDING_NEWS_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


# ============================================================
# WEBFLOW API
# ============================================================

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================
# SLUG GENERATOR
# ============================================================

def make_slug(title):
    slug = title.lower()

    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)

    slug = slug.strip("-")

    # Webflow slug field max length = 256
    return slug[:250]


# ============================================================
# DATE CONVERTER
# ============================================================

def convert_date(date_string):

    try:
        dt = parsedate_to_datetime(date_string)

        # Convert to UTC
        dt = dt.astimezone()

        return dt.isoformat()

    except Exception:
        return datetime.utcnow().isoformat() + "Z"


# ============================================================
# READ RSS
# ============================================================

def read_rss():

    print("Reading RSS feed...")

    feed = feedparser.parse(RSS_URL)

    articles = []

    for entry in feed.entries:

        title = entry.get("title", "").strip()

        url = entry.get("link", "").strip()

        source = ""

        # Try RSS source
        if hasattr(entry, "source"):
            source = entry.source.get("title", "")

        # Fallback
        if not source:
            source = entry.get("author", "")

        # Final fallback
        if not source:
            source = "Unknown"

        source = source.strip()

        date_string = (
            entry.get("published")
            or entry.get("updated")
            or ""
        )

        image_url = ""

        # ----------------------------------------------------
        # Try media content
        # ----------------------------------------------------

        if hasattr(entry, "media_content"):

            try:

                if entry.media_content:
                    image_url = entry.media_content[0].get("url", "")

            except Exception:
                pass

        # ----------------------------------------------------
        # Try media thumbnail
        # ----------------------------------------------------

        if not image_url and hasattr(entry, "media_thumbnail"):

            try:

                if entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get("url", "")

            except Exception:
                pass

        # ----------------------------------------------------
        # Add article
        # ----------------------------------------------------

        if title and url:

            articles.append({
                "title": title,
                "url": url,
                "source": source,
                "date": date_string,
                "image": image_url
            })

    print(f"Found {len(articles)} RSS articles")

    return articles


# ============================================================
# GET EXISTING WEBFLOW ITEMS
# ============================================================

def get_existing_items(collection_id):

    print("Reading existing Webflow items...")

    url = (
        f"https://api.webflow.com/v2/collections/"
        f"{collection_id}/items?limit=100"
    )

    items = []

    offset = 0

    while True:

        params = {
            "limit": 100,
            "offset": offset
        }

        response = requests.get(
            url,
            headers=HEADERS,
            params=params
        )

        if response.status_code != 200:

            print("Could not read Webflow items")

            print(response.status_code)
            print(response.text)

            break

        data = response.json()

        batch = data.get("items", [])

        items.extend(batch)

        if len(batch) < 100:
            break

        offset += 100

    print(f"Found {len(items)} existing items.")

    return items


# ============================================================
# CREATE EXISTING ITEM LOOKUP
# ============================================================

def build_existing_lookup(items):

    lookup = {}

    for item in items:

        field_data = item.get("fieldData", {})

        news_link = field_data.get("news-link")

        # Ticker collection may use news-url
        if not news_link:
            news_link = field_data.get("news-url")

        if news_link:

            lookup[news_link] = item

    return lookup


# ============================================================
# CREATE WEBFLOW ITEM
# ============================================================

def create_item(
    collection_id,
    article,
    collection_type
):

    title = article["title"]

    url = article["url"]

    source = article["source"]

    date_string = article["date"]

    slug = make_slug(title)

    publish_date = convert_date(date_string)

    # --------------------------------------------------------
    # TICKER
    # --------------------------------------------------------

    if collection_type == "ticker":

        field_data = {

            "name": title,

            "news-url": url,

            "source": source,

            "publish-date": publish_date,

            "slug": slug

        }

    # --------------------------------------------------------
    # TRENDING NEWS
    # --------------------------------------------------------

    else:

        field_data = {

            "name": title,

            "news-link": url,

            "source-name": source,

            "publish-date": publish_date,

            "slug": slug

        }

    payload = {
        "fieldData": field_data
    }

    api_url = (
        f"https://api.webflow.com/v2/collections/"
        f"{collection_id}/items"
    )

    response = requests.post(
        api_url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in [200, 201, 202]:

        print(
            f"Created Webflow item: "
            f"{response.status_code}"
        )

        return True

    print("Webflow API error:", response.status_code)
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
    existing_slug=None
):

    title = article["title"]

    url = article["url"]

    source = article["source"]

    date_string = article["date"]

    publish_date = convert_date(date_string)

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT change the existing slug during update.
    #
    # This prevents:
    #
    # "Unique value is already in database"
    #
    # errors when duplicate/old items exist.
    # --------------------------------------------------------

    if collection_type == "ticker":

        field_data = {

            "name": title,

            "news-url": url,

            "source": source,

            "publish-date": publish_date

        }

    else:

        field_data = {

            "name": title,

            "news-link": url,

            "source-name": source,

            "publish-date": publish_date

        }

    payload = {
        "fieldData": field_data
    }

    api_url = (
        f"https://api.webflow.com/v2/collections/"
        f"{collection_id}/items/{item_id}"
    )

    response = requests.patch(
        api_url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in [200, 201, 202]:

        print(
            f"Updated Webflow item: "
            f"{response.status_code}"
        )

        return True

    print("Webflow API error:", response.status_code)
    print(response.text)

    return False


# ============================================================
# SYNC COLLECTION
# ============================================================

def sync_collection(
    collection_id,
    articles,
    collection_type
):

    print("--------------------------------------")
    print("Collection ID:", collection_id)

    existing_items = get_existing_items(collection_id)

    existing_lookup = build_existing_lookup(existing_items)

    created = 0

    updated = 0

    failed = 0

    for article in articles:

        print("--------------------------------------")

        print("Title:", article["title"])

        print("Source:", article["source"])

        print("Date:", article["date"])

        print("URL:", article["url"])

        print("--------------------------------------")

        url = article["url"]

        existing_item = existing_lookup.get(url)

        try:

            if existing_item:

                print("Existing article found.")

                item_id = existing_item.get("id")

                print(
                    "Updating item ID:",
                    item_id
                )

                success = update_item(
                    collection_id,
                    item_id,
                    article,
                    collection_type
                )

                if success:
                    updated += 1
                else:
                    failed += 1

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

        except Exception as e:

            print("Could not sync item:", e)

            failed += 1

    return created, updated, failed


# ============================================================
# SELECT TRENDING NEWS
# MAXIMUM 2 FROM EACH SOURCE
# ============================================================

def select_trending_articles(articles):

    print("")
    print("======================================")
    print("SELECTING TRENDING NEWS")
    print("======================================")

    trending_articles = []

    source_count = {}

    for article in articles:

        source = article["source"].strip()

        if not source:
            source = "Unknown"

        current_count = source_count.get(
            source,
            0
        )

        # -----------------------------------------------
        # MAXIMUM 2 ARTICLES FROM SAME SOURCE
        # -----------------------------------------------

        if current_count >= 2:

            continue

        trending_articles.append(article)

        source_count[source] = current_count + 1

        # -----------------------------------------------
        # STOP AT 10 ARTICLES
        # -----------------------------------------------

        if len(trending_articles) >= 10:

            break

    print("")

    print(
        f"Selected {len(trending_articles)} "
        f"Trending News articles"
    )

    print("")

    print("Source distribution:")

    for source, count in source_count.items():

        print(
            f"  {source}: {count}"
        )

    return trending_articles


# ============================================================
# PUBLISH WEBFLOW SITE
# ============================================================

def publish_site():

    print("")
    print("======================================")
    print("PUBLISHING WEBFLOW SITE")
    print("======================================")

    url = (
        f"https://api.webflow.com/v2/sites/"
        f"{SITE_ID}/publish"
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
        "Webflow publish response:",
        response.status_code
    )

    if response.text:

        print(response.text)

    if response.status_code in [200, 201, 202]:

        print(
            "Webflow site publish request completed."
        )

    else:

        print(
            "Webflow site publish failed."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("======================================")
    print("STARTING RSS → WEBFLOW SYNC")
    print("======================================")

    print(
        "Ticker Collection:",
        TICKER_COLLECTION_ID
    )

    print(
        "Trending News Collection:",
        TRENDING_NEWS_COLLECTION_ID
    )

    print(
        "Site ID:",
        SITE_ID
    )

    print("")

    # --------------------------------------------------------
    # READ RSS
    # --------------------------------------------------------

    articles = read_rss()

    if not articles:

        print("No RSS articles found.")

        return

    # --------------------------------------------------------
    # SORT BY DATE
    # --------------------------------------------------------

    def sort_date(article):

        try:

            return parsedate_to_datetime(
                article["date"]
            )

        except Exception:

            return datetime.min

    articles.sort(
        key=sort_date,
        reverse=True
    )

    # --------------------------------------------------------
    # LATEST 10 FOR TICKER
    # --------------------------------------------------------

    ticker_articles = articles[:10]

    # --------------------------------------------------------
    # TRENDING:
    # MAX 2 FROM EACH SOURCE
    # --------------------------------------------------------

    trending_articles = select_trending_articles(
        articles
    )

    print("")
    print(
        f"Processing latest "
        f"{len(ticker_articles)} articles..."
    )

    # ========================================================
    # TICKER
    # ========================================================

    print("")
    print("======================================")
    print("SYNCING TICKER")
    print("======================================")

    ticker_created, ticker_updated, ticker_failed = (
        sync_collection(
            TICKER_COLLECTION_ID,
            ticker_articles,
            "ticker"
        )
    )

    print("")

    print("TICKER results:")

    print("Created:", ticker_created)

    print("Updated:", ticker_updated)

    print("Failed:", ticker_failed)

    # ========================================================
    # TRENDING NEWS
    # ========================================================

    print("")
    print("======================================")
    print("SYNCING TRENDING NEWS")
    print("======================================")

    trending_created, trending_updated, trending_failed = (
        sync_collection(
            TRENDING_NEWS_COLLECTION_ID,
            trending_articles,
            "trending"
        )
    )

    print("")

    print("TRENDING NEWS results:")

    print("Created:", trending_created)

    print("Updated:", trending_updated)

    print("Failed:", trending_failed)

    # ========================================================
    # PUBLISH
    # ========================================================

    publish_site()

    # ========================================================
    # FINISHED
    # ========================================================

    print("")
    print("======================================")
    print("RSS → WEBFLOW SYNC FINISHED")
    print("======================================")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
