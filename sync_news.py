import os
import requests
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime


# ============================================================
# CONFIGURATION
# ============================================================

WEBFLOW_API_TOKEN = os.environ.get("WEBFLOW_API_TOKEN")
RSS_FEED_URL = os.environ.get("RSS_FEED_URL")
WEBFLOW_TICKER_COLLECTION_ID = os.environ.get("WEBFLOW_COLLECTION_ID")
WEBFLOW_SITE_ID = os.environ.get("WEBFLOW_SITE_ID")

# Your Trending News collection
WEBFLOW_TRENDING_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


# ============================================================
# VALIDATE ENVIRONMENT VARIABLES
# ============================================================

required_variables = {
    "WEBFLOW_API_TOKEN": WEBFLOW_API_TOKEN,
    "RSS_FEED_URL": RSS_FEED_URL,
    "WEBFLOW_COLLECTION_ID": WEBFLOW_TICKER_COLLECTION_ID,
    "WEBFLOW_SITE_ID": WEBFLOW_SITE_ID,
}

missing_variables = [
    name for name, value in required_variables.items()
    if not value
]

if missing_variables:
    print("ERROR: Missing environment variables:")
    for variable in missing_variables:
        print(f" - {variable}")
    raise SystemExit(1)


# ============================================================
# WEBFLOW API
# ============================================================

BASE_URL = "https://api.webflow.com/v2"

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json",
}


# ============================================================
# PRINT HEADER
# ============================================================

print()
print("=" * 50)
print("STARTING RSS → WEBFLOW SYNC")
print("=" * 50)
print()
print(f"Ticker Collection: {WEBFLOW_TICKER_COLLECTION_ID}")
print(f"Trending News Collection: {WEBFLOW_TRENDING_COLLECTION_ID}")
print(f"Site ID: {WEBFLOW_SITE_ID}")
print()


# ============================================================
# READ RSS
# ============================================================

print("Reading RSS feed...")

feed = feedparser.parse(RSS_FEED_URL)

if feed.bozo:
    print("Warning: RSS feed returned a parsing warning.")

articles = []

for entry in feed.entries:

    title = entry.get("title", "").strip()

    link = entry.get("link", "").strip()

    if not title or not link:
        continue

    # --------------------------------------------------------
    # Source / Author
    # --------------------------------------------------------

    source = ""

    if entry.get("author"):
        source = entry.get("author", "").strip()

    elif entry.get("source"):
        source_data = entry.get("source")

        if isinstance(source_data, dict):
            source = source_data.get("title", "").strip()

        else:
            source = str(source_data).strip()

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    published = entry.get("published")

    if not published:
        published = entry.get("updated")

    published_datetime = None

    if published:
        try:
            published_datetime = parsedate_to_datetime(published)
        except Exception:
            try:
                published_datetime = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )
            except Exception:
                published_datetime = None

    if published_datetime is None:
        published_datetime = datetime.now().astimezone()

    articles.append({
        "title": title,
        "link": link,
        "source": source,
        "date": published_datetime,
    })


print(f"Found {len(articles)} RSS articles")


# ============================================================
# SORT BY DATE
# ============================================================

articles.sort(
    key=lambda article: article["date"],
    reverse=True
)


# ============================================================
# PROCESS LATEST 10
# ============================================================

articles = articles[:10]

print(f"Processing latest {len(articles)} articles...")


# ============================================================
# SLUG GENERATOR
# ============================================================

def create_slug(title):
    """
    Create a Webflow-friendly slug.
    """

    import re

    slug = title.lower()

    slug = re.sub(r"[^\w\s-]", "", slug)

    slug = re.sub(r"\s+", "-", slug)

    slug = re.sub(r"-+", "-", slug)

    slug = slug.strip("-")

    return slug[:100]


# ============================================================
# DATE FORMAT
# ============================================================

def format_webflow_date(date_value):

    return date_value.astimezone().isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z"
    )


# ============================================================
# GET EXISTING WEBFLOW ITEMS
# ============================================================

def get_existing_items(collection_id):

    print("Reading existing Webflow items...")

    all_items = []

    offset = 0
    limit = 100

    while True:

        url = (
            f"{BASE_URL}/collections/"
            f"{collection_id}/items"
            f"?limit={limit}&offset={offset}"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:

            print(
                "Could not read Webflow items:",
                response.status_code
            )

            print(response.text)

            return all_items

        data = response.json()

        items = data.get("items", [])

        all_items.extend(items)

        if len(items) < limit:
            break

        offset += limit

    print(f"Found {len(all_items)} existing items.")

    return all_items


# ============================================================
# FIND EXISTING ARTICLE
# ============================================================

def find_existing_article(existing_items, article):

    article_url = article["link"]

    article_slug = create_slug(article["title"])

    for item in existing_items:

        field_data = item.get("fieldData", {})

        # ----------------------------------------------------
        # Check by URL
        # ----------------------------------------------------

        existing_url = (
            field_data.get("news-url")
            or field_data.get("news-link")
            or field_data.get("link")
            or field_data.get("url")
        )

        if existing_url == article_url:
            return item

        # ----------------------------------------------------
        # Check by slug
        # ----------------------------------------------------

        existing_slug = field_data.get("slug")

        if existing_slug == article_slug:
            return item

    return None


# ============================================================
# CREATE FIELD DATA
# ============================================================

def build_ticker_field_data(article):

    return {
        "name": article["title"],
        "news-url": article["link"],
        "source": article["source"],
        "publish-date": format_webflow_date(article["date"]),
        "slug": create_slug(article["title"]),
    }


def build_trending_field_data(article):

    return {
        "name": article["title"],
        "news-link": article["link"],
        "source-name": article["source"],
        "publish-date": format_webflow_date(article["date"]),
        "slug": create_slug(article["title"]),
        # Image intentionally disabled
        # "news-image": ...
    }


# ============================================================
# CREATE WEBFLOW ITEM
# ============================================================

def create_webflow_item(collection_id, field_data):

    url = f"{BASE_URL}/collections/{collection_id}/items"

    payload = {
        "fieldData": field_data
    }

    response = requests.post(
        url,
        headers=HEADERS,
        json=payload,
        timeout=30
    )

    # --------------------------------------------------------
    # Webflow can return:
    #
    # 200 = OK
    # 201 = Created
    # 202 = Accepted
    #
    # ALL THREE ARE SUCCESSFUL.
    # --------------------------------------------------------

    if response.status_code not in (200, 201, 202):

        print(
            "Webflow API error:",
            response.status_code
        )

        print(response.text)

        return None

    try:
        return response.json()

    except Exception:

        return {
            "status_code": response.status_code
        }


# ============================================================
# UPDATE WEBFLOW ITEM
# ============================================================

def update_webflow_item(
    collection_id,
    item_id,
    field_data
):

    url = (
        f"{BASE_URL}/collections/"
        f"{collection_id}/items/{item_id}"
    )

    payload = {
        "fieldData": field_data
    }

    response = requests.patch(
        url,
        headers=HEADERS,
        json=payload,
        timeout=30
    )

    # --------------------------------------------------------
    # 200 / 201 / 202 are successful
    # --------------------------------------------------------

    if response.status_code not in (200, 201, 202):

        print(
            "Webflow API error:",
            response.status_code
        )

        print(response.text)

        return None

    try:
        return response.json()

    except Exception:

        return {
            "status_code": response.status_code
        }


# ============================================================
# SYNC COLLECTION
# ============================================================

def sync_collection(
    collection_id,
    collection_name,
    field_data_function
):

    print()
    print("=" * 50)
    print(f"SYNCING {collection_name}")
    print("=" * 50)

    print(f"Collection ID: {collection_id}")

    existing_items = get_existing_items(collection_id)

    created = 0
    updated = 0
    failed = 0

    # --------------------------------------------------------
    # Process each RSS article
    # --------------------------------------------------------

    for article in articles:

        print("-" * 40)

        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print(
            f"Date: "
            f"{article['date'].strftime('%a, %d %b %Y %H:%M:%S %Z')}"
        )
        print(f"URL: {article['link']}")

        print("-" * 40)

        existing_item = find_existing_article(
            existing_items,
            article
        )

        field_data = field_data_function(article)

        # ----------------------------------------------------
        # UPDATE EXISTING
        # ----------------------------------------------------

        if existing_item:

            item_id = existing_item.get("id")

            print("Existing article found.")
            print(f"Updating item ID: {item_id}")

            result = update_webflow_item(
                collection_id,
                item_id,
                field_data
            )

            if result:

                print(
                    "Updated Webflow item:",
                    result.get(
                        "status_code",
                        200
                    )
                )

                updated += 1

            else:

                print("Could not sync item.")

                failed += 1

        # ----------------------------------------------------
        # CREATE NEW
        # ----------------------------------------------------

        else:

            print("New article found.")

            result = create_webflow_item(
                collection_id,
                field_data
            )

            if result:

                print(
                    "Created Webflow item:",
                    result.get("id", "success")
                )

                created += 1

            else:

                print("Could not sync item.")

                failed += 1

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    print()
    print(f"{collection_name} results:")
    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")

    return created, updated, failed


# ============================================================
# SYNC TICKER
# ============================================================

ticker_created, ticker_updated, ticker_failed = sync_collection(
    WEBFLOW_TICKER_COLLECTION_ID,
    "TICKER",
    build_ticker_field_data
)


# ============================================================
# SYNC TRENDING NEWS
# ============================================================

trending_created, trending_updated, trending_failed = sync_collection(
    WEBFLOW_TRENDING_COLLECTION_ID,
    "TRENDING NEWS",
    build_trending_field_data
)


# ============================================================
# PUBLISH WEBFLOW SITE
# ============================================================

print()
print("=" * 50)
print("PUBLISHING WEBFLOW SITE")
print("=" * 50)

publish_url = (
    f"{BASE_URL}/sites/"
    f"{WEBFLOW_SITE_ID}/publish"
)

publish_payload = {
    "publishToWebflowSubdomain": True
}

publish_response = requests.post(
    publish_url,
    headers=HEADERS,
    json=publish_payload,
    timeout=30
)


if publish_response.status_code not in (200, 201, 202):

    print(
        "Webflow publish error:",
        publish_response.status_code
    )

    print(publish_response.text)

else:

    print(
        "Webflow publish response:",
        publish_response.status_code
    )

    print("Webflow site publish request completed.")


# ============================================================
# FINISHED
# ============================================================

print()
print("=" * 50)
print("RSS → WEBFLOW SYNC FINISHED")
print("=" * 50)
