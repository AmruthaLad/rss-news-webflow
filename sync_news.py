import os
import re
import html
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import timezone


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

RSS_URL = os.environ["RSS_FEED_URL"]
WEBFLOW_TOKEN = os.environ["WEBFLOW_API_TOKEN"]
SITE_ID = os.environ["WEBFLOW_SITE_ID"]


# ============================================================
# COLLECTION IDS
# ============================================================

TICKER_COLLECTION_ID = "69b2a1bd8d44d2270008a256"

TRENDING_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


# ============================================================
# WEBFLOW API
# ============================================================

def webflow_request(
    method,
    url,
    data=None
):

    headers = {
        "Authorization": f"Bearer {WEBFLOW_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Version": "1.0.0",
    }

    request = urllib.request.Request(
        url,
        method=method,
        headers=headers
    )

    if data is not None:

        request.data = json.dumps(
            data
        ).encode("utf-8")

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            response_body = response.read().decode(
                "utf-8"
            )

            return (
                response.status,
                response_body
            )

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print("")
        print(
            f"Webflow API error: {error.code}"
        )

        print(error_body)

        raise


# ============================================================
# RSS
# ============================================================

def fetch_rss():

    print("")
    print(
        "Reading RSS feed..."
    )

    request = urllib.request.Request(
        RSS_URL,
        headers={
            "User-Agent":
                "RSS-News-Webflow-Automation/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read()


def clean_text(value):

    if not value:
        return ""

    value = html.unescape(
        value
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value
    )

    return " ".join(
        value.split()
    ).strip()


def parse_rss(data):

    root = ET.fromstring(
        data
    )

    articles = []

    for item in root.findall(
        ".//item"
    ):

        title = clean_text(
            item.findtext("title")
        )

        link = clean_text(
            item.findtext("link")
        )

        pub_date = clean_text(
            item.findtext("pubDate")
        )

        if not title or not link:
            continue

        articles.append(
            {
                "title": title,
                "link": link,
                "pub_date": pub_date
            }
        )

    return articles


# ============================================================
# DATE
# ============================================================

def convert_date(date_string):

    if not date_string:
        return ""

    try:

        date = parsedate_to_datetime(
            date_string
        )

        if date.tzinfo is not None:

            date = date.astimezone(
                timezone.utc
            )

        return date.strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    except Exception as error:

        print(
            f"Date conversion failed: {error}"
        )

        return ""


# ============================================================
# SOURCE
# ============================================================

def get_source(link):

    link_lower = link.lower()

    if "venturebeat.com" in link_lower:
        return "VentureBeat"

    if "techcrunch.com" in link_lower:
        return "TechCrunch"

    if "intelligentautomation.network" in link_lower:
        return "Intelligent Automation Network"

    if "artificialintelligence-news.com" in link_lower:
        return "Artificial Intelligence News"

    if "diginomica.com" in link_lower:
        return "Diginomica"

    if "cio.com" in link_lower:
        return "CIO"

    return "News"


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

    return slug[:90]


# ============================================================
# GET EXISTING WEBFLOW ITEMS
# ============================================================

def get_existing_items(
    collection_id
):

    url = (
        f"https://api.webflow.com/v2/collections/"
        f"{collection_id}/items"
    )

    try:

        status, response = webflow_request(
            "GET",
            url
        )

        data = json.loads(
            response
        )

        return data.get(
            "items",
            []
        )

    except Exception as error:

        print(
            f"Could not read existing items: {error}"
        )

        return []


# ============================================================
# CREATE / UPDATE ITEM
# ============================================================

def sync_item(
    collection_id,
    article,
    link_field,
    source_field
):

    title = article["title"]
    link = article["link"]
    pub_date = article["pub_date"]

    source = get_source(
        link
    )

    slug = create_slug(
        title
    )

    webflow_date = convert_date(
        pub_date
    )


    # --------------------------------------------------------
    # IMPORTANT:
    # IMAGE IS INTENTIONALLY NOT INCLUDED
    # --------------------------------------------------------

    field_data = {

        "name":
            title,

        "slug":
            slug,

        link_field:
            link,

        source_field:
            source,

        "publish-date":
            webflow_date
    }


    # --------------------------------------------------------
    # FIND EXISTING ITEM
    # --------------------------------------------------------

    existing_items = get_existing_items(
        collection_id
    )

    existing_item = None

    for item in existing_items:

        item_field_data = item.get(
            "fieldData",
            {}
        )

        existing_link = item_field_data.get(
            link_field,
            ""
        )

        if existing_link == link:

            existing_item = item
            break


    # --------------------------------------------------------
    # UPDATE EXISTING ITEM
    # --------------------------------------------------------

    if existing_item:

        item_id = existing_item.get(
            "id"
        )

        update_url = (
            f"https://api.webflow.com/v2/"
            f"collections/{collection_id}/"
            f"items/{item_id}"
        )

        payload = {

            "fieldData":
                field_data
        }

        status, response = webflow_request(
            "PATCH",
            update_url,
            payload
        )

        print(
            f"Updated Webflow item: "
            f"{status}"
        )

        return "updated"


    # --------------------------------------------------------
    # CREATE NEW ITEM
    # --------------------------------------------------------

    create_url = (
        f"https://api.webflow.com/v2/"
        f"collections/{collection_id}/items"
    )

    payload = {

        "isArchived":
            False,

        "isDraft":
            False,

        "fieldData":
            field_data
    }

    status, response = webflow_request(
        "POST",
        create_url,
        payload
    )

    print(
        f"Created Webflow item: "
        f"{status}"
    )

    return "created"


# ============================================================
# PUBLISH
# ============================================================

def publish_site():

    print("")
    print(
        "Publishing Webflow site..."
    )

    publish_url = (
        f"https://api.webflow.com/v2/sites/"
        f"{SITE_ID}/publish"
    )

    payload = {

        "publishToWebflowSubdomain":
            True
    }

    try:

        status, response = webflow_request(
            "POST",
            publish_url,
            payload
        )

        print(
            f"Webflow publish response: "
            f"{status}"
        )

        print(
            "Webflow site publish request completed."
        )

    except urllib.error.HTTPError:

        print(
            "Webflow publishing failed."
        )


# ============================================================
# SYNC COLLECTION
# ============================================================

def sync_collection(
    collection_name,
    collection_id,
    link_field,
    source_field,
    articles
):

    print("")
    print(
        "======================================"
    )

    print(
        f"SYNCING {collection_name}"
    )

    print(
        "======================================"
    )

    print(
        f"Collection ID: {collection_id}"
    )

    created = 0
    updated = 0
    failed = 0


    for article in articles:

        print("")
        print(
            "--------------------------------------"
        )

        print(
            f"Title: {article['title']}"
        )

        print(
            f"Source: "
            f"{get_source(article['link'])}"
        )

        print(
            f"Date: "
            f"{article['pub_date']}"
        )

        print(
            f"URL: "
            f"{article['link']}"
        )

        print(
            "--------------------------------------"
        )

        try:

            result = sync_item(
                collection_id,
                article,
                link_field,
                source_field
            )

            if result == "created":
                created += 1

            elif result == "updated":
                updated += 1

        except Exception as error:

            failed += 1

            print(
                f"Could not sync item: {error}"
            )


    print("")
    print(
        f"{collection_name} results:"
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

    return created + updated


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print(
        "======================================"
    )

    print(
        "STARTING RSS → WEBFLOW SYNC"
    )

    print(
        "======================================"
    )

    print(
        f"Ticker Collection: "
        f"{TICKER_COLLECTION_ID}"
    )

    print(
        f"Trending News Collection: "
        f"{TRENDING_COLLECTION_ID}"
    )

    print(
        f"Site ID: {SITE_ID}"
    )


    # --------------------------------------------------------
    # FETCH RSS
    # --------------------------------------------------------

    rss_data = fetch_rss()

    articles = parse_rss(
        rss_data
    )

    print("")
    print(
        f"Found {len(articles)} RSS articles"
    )


    if not articles:

        print(
            "No RSS articles found."
        )

        return


    # --------------------------------------------------------
    # PROCESS LATEST 10
    # --------------------------------------------------------

    articles = articles[:10]

    print(
        f"Processing latest "
        f"{len(articles)} articles..."
    )


    # --------------------------------------------------------
    # TICKER
    #
    # Ticker fields:
    # name
    # slug
    # news-url
    # source
    # publish-date
    # --------------------------------------------------------

    ticker_count = sync_collection(

        "TICKER",

        TICKER_COLLECTION_ID,

        "news-url",

        "source",

        articles
    )


    # --------------------------------------------------------
    # TRENDING NEWS
    #
    # Trending News fields:
    # name
    # slug
    # news-link
    # source-name
    # publish-date
    # --------------------------------------------------------

    trending_count = sync_collection(

        "TRENDING NEWS",

        TRENDING_COLLECTION_ID,

        "news-link",

        "source-name",

        articles
    )


    # --------------------------------------------------------
    # PUBLISH
    # --------------------------------------------------------

    if (
        ticker_count > 0
        or trending_count > 0
    ):

        publish_site()


    print("")
    print(
        "======================================"
    )

    print(
        "RSS → WEBFLOW SYNC FINISHED"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()
