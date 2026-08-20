import os
import requests
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
import unicodedata

# ============================================================
# CONFIGURATION
# ============================================================

WEBFLOW_API_TOKEN = os.environ["WEBFLOW_API_TOKEN"]
RSS_FEED_URL = os.environ["RSS_FEED_URL"]

TICKER_COLLECTION_ID = os.environ["WEBFLOW_COLLECTION_ID"]
TRENDING_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"
WEBFLOW_SITE_ID = os.environ["WEBFLOW_SITE_ID"]

WEBFLOW_API = "https://api.webflow.com/v2"

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json"
}

# Number of RSS articles to process
RSS_LIMIT = 10


# ============================================================
# HELPERS
# ============================================================

def make_slug(title):
    """
    Create a Webflow-safe slug.
    Only used when CREATING a new item.
    """

    value = unicodedata.normalize("NFKD", title)
    value = value.encode("ascii", "ignore").decode("ascii")

    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")

    return value[:150]


def normalize_url(url):
    """
    Normalize URLs so matching works correctly.
    """

    if not url:
        return ""

    url = url.strip()

    # Remove trailing slash
    url = url.rstrip("/")

    return url.lower()


def parse_date(entry):
    """
    Convert RSS publication date into ISO format.
    """

    date_value = (
        entry.get("published")
        or entry.get("updated")
        or entry.get("pubDate")
    )

    if not date_value:
        return datetime.utcnow().isoformat() + "Z"

    try:
        dt = parsedate_to_datetime(date_value)

        if dt.tzinfo is None:
            return dt.isoformat() + "Z"

        return dt.astimezone().isoformat().replace("+00:00", "Z")

    except Exception:
        return datetime.utcnow().isoformat() + "Z"


def get_source(entry):
    """
    Get the source/author value from RSS.
    """

    # Try author first
    author = entry.get("author")

    if author:
        return author.strip()

    # Try source
    source = entry.get("source")

    if isinstance(source, dict):
        source_name = source.get("title")

        if source_name:
            return source_name.strip()

    if source:
        return str(source).strip()

    # Try dc_creator
    creator = entry.get("dc_creator")

    if creator:
        return creator.strip()

    return "Unknown"


# ============================================================
# READ RSS
# ============================================================

def read_rss():

    print("Reading RSS feed...")

    feed = feedparser.parse(RSS_FEED_URL)

    articles = []

    for entry in feed.entries:

        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            continue

        article = {
            "title": title,
            "url": link,
            "source": get_source(entry),
            "date": parse_date(entry)
        }

        articles.append(article)

    print(f"Found {len(articles)} RSS articles")

    # Latest articles
    articles = articles[:RSS_LIMIT]

    print(f"Processing latest {len(articles)} articles...")

    return articles


# ============================================================
# GET ALL WEBFLOW ITEMS
# ============================================================

def get_webflow_items(collection_id):

    print("Reading existing Webflow items...")

    all_items = []

    offset = 0
    limit = 100

    while True:

        url = (
            f"{WEBFLOW_API}/collections/"
            f"{collection_id}/items"
            f"?limit={limit}&offset={offset}"
        )

        response = requests.get(
            url,
            headers=HEADERS
        )

        if response.status_code != 200:

            print(
                "Error reading Webflow items:",
                response.status_code,
                response.text
            )

            return all_items

        data = response.json()

        items = data.get("items", [])

        all_items.extend(items)

        pagination = data.get("pagination", {})

        total = pagination.get("total", len(all_items))

        if len(all_items) >= total:
            break

        offset += limit

    print(f"Found {len(all_items)} existing items.")

    return all_items


# ============================================================
# FIND EXISTING ITEM BY NEWS URL
# ============================================================

def find_existing_item(items, article_url):

    target_url = normalize_url(article_url)

    for item in items:

        field_data = item.get("fieldData", {})

        existing_url = (
            field_data.get("news-link")
            or field_data.get("news-url")
            or field_data.get("link")
            or ""
        )

        if normalize_url(existing_url) == target_url:

            return item

    return None


# ============================================================
# UPDATE EXISTING ITEM
# ============================================================

def update_item(
    collection_id,
    item,
    article,
    collection_type
):

    item_id = item.get("id")

    print(f"Existing article found.")
    print(f"Updating item ID: {item_id}")

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # DO NOT SEND SLUG WHEN UPDATING.
    #
    # This prevents:
    #
    # Validation Error:
    # Unique value is already in database
    # --------------------------------------------------------

    if collection_type == "ticker":

        field_data = {
            "name": article["title"],
            "news-url": article["url"],
            "source": article["source"],
            "publish-date": article["date"]
        }

    else:

        field_data = {
            "name": article["title"],
            "news-link": article["url"],
            "source-name": article["source"],
            "publish-date": article["date"]
        }

    payload = {
        "fieldData": field_data
    }

    url = (
        f"{WEBFLOW_API}/collections/"
        f"{collection_id}/items/"
        f"{item_id}"
    )

    response = requests.patch(
        url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in [200, 201]:

        print(
            f"Updated Webflow item: "
            f"{response.status_code}"
        )

        return True

    print(
        "Webflow API error:",
        response.status_code
    )

    print(response.text)

    return False


# ============================================================
# CREATE NEW ITEM
# ============================================================

def create_item(
    collection_id,
    article,
    collection_type
):

    print("New article found.")

    slug = make_slug(article["title"])

    if collection_type == "ticker":

        field_data = {
            "name": article["title"],
            "slug": slug,
            "news-url": article["url"],
            "source": article["source"],
            "publish-date": article["date"]
        }

    else:

        field_data = {
            "name": article["title"],
            "slug": slug,
            "news-link": article["url"],
            "source-name": article["source"],
            "publish-date": article["date"]
        }

    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data
    }

    url = (
        f"{WEBFLOW_API}/collections/"
        f"{collection_id}/items"
    )

    response = requests.post(
        url,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in [200, 201, 202]:

        print(
            f"Created Webflow item: "
            f"{response.status_code}"
        )

        return True

    print(
        "Webflow API error:",
        response.status_code
    )

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

    if collection_type == "ticker":

        print("\n" + "=" * 50)
        print("SYNCING TICKER")
        print("=" * 50)

    else:

        print("\n" + "=" * 50)
        print("SYNCING TRENDING NEWS")
        print("=" * 50)

    print(f"Collection ID: {collection_id}")

    existing_items = get_webflow_items(
        collection_id
    )

    created = 0
    updated = 0
    failed = 0

    for article in articles:

        print("\n" + "-" * 40)

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

        print("-" * 40)

        existing_item = find_existing_item(
            existing_items,
            article["url"]
        )

        if existing_item:

            success = update_item(
                collection_id,
                existing_item,
                article,
                collection_type
            )

            if success:
                updated += 1
            else:
                failed += 1

        else:

            success = create_item(
                collection_id,
                article,
                collection_type
            )

            if success:
                created += 1
            else:
                failed += 1

    print("\n" + "=" * 50)

    if collection_type == "ticker":

        print("TICKER results:")

    else:

        print("TRENDING NEWS results:")

    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")


# ============================================================
# PUBLISH WEBFLOW SITE
# ============================================================

def publish_site():

    print("\n" + "=" * 50)
    print("PUBLISHING WEBFLOW SITE")
    print("=" * 50)

    url = (
        f"{WEBFLOW_API}/sites/"
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
        "Webflow publish response:",
        response.status_code
    )

    if response.status_code in [200, 201, 202]:

        print(
            "Webflow site publish request completed."
        )

    else:

        print(
            "Webflow publish error:"
        )

        print(response.text)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 50)
    print("STARTING RSS → WEBFLOW SYNC")
    print("=" * 50)

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
    # SYNC TICKER
    # --------------------------------------------------------

    sync_collection(
        TICKER_COLLECTION_ID,
        articles,
        "ticker"
    )

    # --------------------------------------------------------
    # SYNC TRENDING NEWS
    # --------------------------------------------------------

    sync_collection(
        TRENDING_COLLECTION_ID,
        articles,
        "trending"
    )

    # --------------------------------------------------------
    # PUBLISH
    # --------------------------------------------------------

    publish_site()

    print("\n" + "=" * 50)
    print("RSS → WEBFLOW SYNC FINISHED")
    print("=" * 50)


if __name__ == "__main__":
    main()
