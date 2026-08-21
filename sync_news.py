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
WEBFLOW_SITE_ID = os.environ["WEBFLOW_SITE_ID"]

# Existing Webflow collection IDs
TICKER_COLLECTION_ID = os.environ["WEBFLOW_COLLECTION_ID"]
TRENDING_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


# ============================================================
# SIX APPROVED RSS SOURCES
# ============================================================

RSS_FEEDS = [
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/category/ai/feed/"
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/"
    },
    {
        "name": "Intelligent Automation Network",
        "url": "https://www.intelligentautomation.network/rss/articles"
    },
    {
        "name": "Artificial Intelligence News",
        "url": "https://www.artificialintelligence-news.com/feed/"
    },
    {
        "name": "Diginomica",
        "url": "https://diginomica.com/feed"
    },
    {
        "name": "CIO",
        "url": "https://www.cio.com/category/digital-transformation/feed/"
    }
]


# ============================================================
# SETTINGS
# ============================================================

MAX_ARTICLES_PER_SOURCE = 2

# 6 sources × 2 articles
MAX_TOTAL_ARTICLES = len(RSS_FEEDS) * MAX_ARTICLES_PER_SOURCE

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================
# DATE PARSING
# ============================================================

def parse_rss_date(entry):

    date_string = (
        entry.get("published")
        or entry.get("updated")
        or ""
    )

    if not date_string:
        return None

    try:

        dt = parsedate_to_datetime(
            date_string
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:

        try:

            dt = datetime.fromisoformat(
                date_string.replace(
                    "Z",
                    "+00:00"
                )
            )

            if dt.tzinfo is None:

                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(
                timezone.utc
            )

        except Exception:

            return None


def format_webflow_date(date_value):

    if not date_value:
        return ""

    return date_value.strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


# ============================================================
# SLUG
# ============================================================

def create_slug(title):

    slug = title.lower()

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        slug
    )

    slug = slug.strip("-")

    return slug[:150]


# ============================================================
# READ ONE RSS FEED
# ============================================================

def read_feed(source_name, feed_url):

    print("")
    print("=" * 60)
    print(f"READING: {source_name}")
    print(f"FEED: {feed_url}")
    print("=" * 60)

    try:

        feed = feedparser.parse(
            feed_url
        )

    except Exception as error:

        print(
            f"Could not read {source_name}: {error}"
        )

        return []

    articles = []

    for entry in feed.entries:

        title = (
            entry.get("title")
            or ""
        ).strip()

        link = (
            entry.get("link")
            or ""
        ).strip()

        if not title or not link:
            continue

        published_date = parse_rss_date(
            entry
        )

        if not published_date:

            print(
                f"Skipping article without valid date: "
                f"{title}"
            )

            continue

        articles.append(
            {
                "title": title,
                "link": link,
                "source": source_name,
                "date": published_date
            }
        )

    # --------------------------------------------------------
    # Newest first
    # --------------------------------------------------------

    articles.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    print(
        f"Found {len(articles)} articles "
        f"from {source_name}"
    )

    # --------------------------------------------------------
    # ONLY 2 FROM THIS SOURCE
    # --------------------------------------------------------

    selected = articles[
        :MAX_ARTICLES_PER_SOURCE
    ]

    print(
        f"Selected {len(selected)} "
        f"newest articles from {source_name}"
    )

    return selected


# ============================================================
# READ ALL SIX SOURCES
# ============================================================

def read_all_feeds():

    all_articles = []

    for feed in RSS_FEEDS:

        source_name = feed["name"]
        feed_url = feed["url"]

        source_articles = read_feed(
            source_name,
            feed_url
        )

        all_articles.extend(
            source_articles
        )

    # --------------------------------------------------------
    # Sort all selected articles newest first
    # --------------------------------------------------------

    all_articles.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    print("")
    print("=" * 60)
    print(
        f"TOTAL ARTICLES SELECTED: "
        f"{len(all_articles)}"
    )
    print("=" * 60)

    for article in all_articles:

        print(
            f"{article['source']} | "
            f"{article['date'].strftime('%Y-%m-%d %H:%M:%S UTC')} | "
            f"{article['title']}"
        )

    return all_articles


# ============================================================
# WEBFLOW API REQUEST HELPERS
# ============================================================

def get_collection_items(collection_id):

    print("")
    print(
        f"Reading existing Webflow items: "
        f"{collection_id}"
    )

    all_items = []

    offset = 0
    limit = 100

    while True:

        url = (
            f"{WEBFLOW_API_BASE}/collections/"
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
                "Webflow API error:",
                response.status_code
            )

            print(
                response.text
            )

            return all_items

        data = response.json()

        items = data.get(
            "items",
            []
        )

        all_items.extend(
            items
        )

        if len(items) < limit:

            break

        offset += limit

    print(
        f"Found {len(all_items)} existing items."
    )

    return all_items


def find_existing_item(
    existing_items,
    article_url,
    link_field
):

    for item in existing_items:

        field_data = item.get(
            "fieldData",
            {}
        )

        existing_url = field_data.get(
            link_field,
            ""
        )

        if (
            existing_url.rstrip("/")
            .lower()
            ==
            article_url.rstrip("/")
            .lower()
        ):

            return item

    return None


# ============================================================
# CREATE ITEM
# ============================================================

def create_item(
    collection_id,
    article,
    link_field,
    source_field
):

    field_data = {

        "name":
            article["title"],

        "slug":
            create_slug(
                article["title"]
            ),

        link_field:
            article["link"],

        source_field:
            article["source"],

        "publish-date":
            format_webflow_date(
                article["date"]
            )
    }


    # --------------------------------------------------------
    # IMAGE DISABLED FOR NOW
    # --------------------------------------------------------

    # If you want to add image later:
    #
    # field_data["news-image"] = {
    #     "url": image_url,
    #     "alt": article["title"]
    # }


    payload = {

        "isArchived":
            False,

        "isDraft":
            False,

        "fieldData":
            field_data
    }


    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items"
    )


    response = requests.post(
        url,
        headers=HEADERS,
        json=payload,
        timeout=30
    )


    if response.status_code in (
        200,
        201,
        202
    ):

        print(
            f"Created Webflow item: "
            f"{response.status_code}"
        )

        return True


    print(
        "Webflow API error:",
        response.status_code
    )

    print(
        response.text
    )

    return False


# ============================================================
# UPDATE EXISTING ITEM
# ============================================================

def update_item(
    collection_id,
    item_id,
    article,
    link_field,
    source_field
):

    # --------------------------------------------------------
    # IMPORTANT:
    # DO NOT SEND SLUG WHEN UPDATING.
    #
    # This avoids the Webflow:
    #
    # "Unique value is already in database"
    #
    # error.
    # --------------------------------------------------------

    field_data = {

        "name":
            article["title"],

        link_field:
            article["link"],

        source_field:
            article["source"],

        "publish-date":
            format_webflow_date(
                article["date"]
            )
    }


    payload = {

        "fieldData":
            field_data
    }


    url = (
        f"{WEBFLOW_API_BASE}/collections/"
        f"{collection_id}/items/"
        f"{item_id}"
    )


    response = requests.patch(
        url,
        headers=HEADERS,
        json=payload,
        timeout=30
    )


    if response.status_code in (
        200,
        201,
        202
    ):

        print(
            f"Updated Webflow item: "
            f"{response.status_code}"
        )

        return True


    print(
        "Webflow API error:",
        response.status_code
    )

    print(
        response.text
    )

    return False


# ============================================================
# SYNC ONE COLLECTION
# ============================================================

def sync_collection(
    collection_name,
    collection_id,
    articles,
    link_field,
    source_field
):

    print("")
    print("=" * 60)
    print(
        f"SYNCING {collection_name.upper()}"
    )
    print("=" * 60)

    existing_items = get_collection_items(
        collection_id
    )

    created = 0
    updated = 0
    failed = 0


    for article in articles:

        print("")
        print("-" * 60)

        print(
            f"Title: {article['title']}"
        )

        print(
            f"Source: {article['source']}"
        )

        print(
            f"Date: "
            f"{article['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        print(
            f"URL: {article['link']}"
        )

        print("-" * 60)


        existing_item = find_existing_item(
            existing_items,
            article["link"],
            link_field
        )


        try:

            if existing_item:

                item_id = existing_item.get(
                    "id"
                )

                print(
                    "Existing article found."
                )

                print(
                    f"Updating item ID: {item_id}"
                )

                success = update_item(
                    collection_id,
                    item_id,
                    article,
                    link_field,
                    source_field
                )

                if success:

                    updated += 1

            else:

                print(
                    "New article found."
                )

                success = create_item(
                    collection_id,
                    article,
                    link_field,
                    source_field
                )

                if success:

                    created += 1

        except Exception as error:

            failed += 1

            print(
                f"Could not sync item: {error}"
            )


    print("")
    print("=" * 60)

    print(
        f"{collection_name.upper()} RESULTS"
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

    print("=" * 60)


# ============================================================
# PUBLISH WEBFLOW
# ============================================================

def publish_webflow():

    print("")
    print("=" * 60)
    print("PUBLISHING WEBFLOW SITE")
    print("=" * 60)

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
        json=payload,
        timeout=30
    )

    print(
        f"Webflow publish response: "
        f"{response.status_code}"
    )

    if response.status_code in (
        200,
        201,
        202
    ):

        print(
            "Webflow site publish request completed."
        )

    else:

        print(
            response.text
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 60)
    print("STARTING RSS → WEBFLOW SYNC")
    print("=" * 60)

    print("")
    print(
        "Approved RSS sources:"
    )

    for feed in RSS_FEEDS:

        print(
            f"- {feed['name']}"
        )

    print("")
    print(
        f"Maximum {MAX_ARTICLES_PER_SOURCE} "
        f"articles per source"
    )

    print(
        f"Maximum {MAX_TOTAL_ARTICLES} "
        f"articles in total"
    )


    # --------------------------------------------------------
    # READ ONLY THE SIX APPROVED FEEDS
    # --------------------------------------------------------

    articles = read_all_feeds()


    if not articles:

        print(
            "No articles found."
        )

        return


    # --------------------------------------------------------
    # TICKER
    # --------------------------------------------------------

    sync_collection(

        collection_name="Ticker",

        collection_id=
            TICKER_COLLECTION_ID,

        articles=articles,

        link_field=
            "news-url",

        source_field=
            "source"
    )


    # --------------------------------------------------------
    # TRENDING NEWS
    # --------------------------------------------------------

    sync_collection(

        collection_name=
            "Trending News",

        collection_id=
            TRENDING_COLLECTION_ID,

        articles=articles,

        link_field=
            "news-link",

        source_field=
            "source-name"
    )


    # --------------------------------------------------------
    # PUBLISH
    # --------------------------------------------------------

    publish_webflow()


    print("")
    print("=" * 60)
    print(
        "RSS → WEBFLOW SYNC FINISHED"
    )
    print("=" * 60)


if __name__ == "__main__":

    main()
