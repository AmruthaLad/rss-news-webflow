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

TRENDING_NEWS_COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


# ============================================================
# WEBFLOW API
# ============================================================

def collection_items_url(collection_id):

    return (
        f"https://api.webflow.com/v2/collections/"
        f"{collection_id}/items"
    )


WEBFLOW_PUBLISH_URL = (
    f"https://api.webflow.com/v2/sites/"
    f"{SITE_ID}/publish"
)


# ============================================================
# FETCH RSS
# ============================================================

def fetch_rss():

    print("Reading RSS feed...")

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


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(
        r"<[^>]+>",
        "",
        value
    )

    return " ".join(
        value.split()
    ).strip()


# ============================================================
# PARSE RSS
# ============================================================

def parse_rss(data):

    root = ET.fromstring(data)

    articles = []

    for item in root.findall(".//item"):

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
                "pub_date": pub_date,
            }
        )

    return articles


# ============================================================
# DATE CONVERSION
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
# SOURCE NAME
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
# CREATE SLUG
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
# WEBFLOW REQUEST
# ============================================================

def webflow_request(
    method,
    url,
    data=None
):

    headers = {
        "Authorization":
            f"Bearer {WEBFLOW_TOKEN}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json",
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

            return (
                response.status,
                response.read().decode(
                    "utf-8"
                )
            )


    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            f"Webflow API error: {error.code}"
        )

        print(error_body)

        raise


# ============================================================
# GET EXISTING ITEMS
# ============================================================

def get_existing_items(collection_id):

    print(
        "Reading existing Webflow items..."
    )

    all_items = []

    offset = 0

    limit = 100


    while True:

        url = (
            collection_items_url(
                collection_id
            )
            + f"?offset={offset}&limit={limit}"
        )

        status, response = webflow_request(
            "GET",
            url
        )

        data = json.loads(
            response
        )

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


# ============================================================
# FIND EXISTING ARTICLE
# ============================================================

def find_existing_article(
    existing_items,
    link,
    link_field
):

    for item in existing_items:

        field_data = item.get(
            "fieldData",
            {}
        )

        existing_link = field_data.get(
            link_field,
            ""
        )

        if existing_link == link:

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

    title = article["title"]

    link = article["link"]

    pub_date = article["pub_date"]

    source = get_source(
        link
    )

    webflow_date = convert_date(
        pub_date
    )

    slug = create_slug(
        title
    )


    # ========================================================
    # COMMON FIELDS
    # ========================================================

    field_data = {

        "name":
            title,

        link_field:
            link,

        source_field:
            source,

        "publish-date":
            webflow_date,

        "slug":
            slug,
    }


    # ========================================================
    # IMAGE DISABLED FOR NOW
    #
    # "news-image": {
    #     "url": image_url,
    #     "alt": title
    # }
    #
    # ========================================================


    payload = {

        "isArchived":
            False,

        "isDraft":
            False,

        "fieldData":
            field_data,
    }


    status, response = webflow_request(
        "POST",
        collection_items_url(
            collection_id
        ),
        payload
    )


    print(
        f"Created Webflow item: {status}"
    )

    return response


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

    title = article["title"]

    link = article["link"]

    pub_date = article["pub_date"]

    source = get_source(
        link
    )

    webflow_date = convert_date(
        pub_date
    )


    # ========================================================
    # IMPORTANT
    #
    # DO NOT SEND SLUG WHEN UPDATING EXISTING ITEMS.
    #
    # This prevents:
    #
    # Unique value is already in database
    #
    # ========================================================

    field_data = {

        "name":
            title,

        link_field:
            link,

        source_field:
            source,

        "publish-date":
            webflow_date,
    }


    # ========================================================
    # IMAGE DISABLED FOR NOW
    # ========================================================

    # field_data["news-image"] = {
    #     "url": image_url,
    #     "alt": title
    # }


    payload = {

        "fieldData":
            field_data
    }


    url = (
        collection_items_url(
            collection_id
        )
        + f"/{item_id}"
    )


    status, response = webflow_request(
        "PATCH",
        url,
        payload
    )


    print(
        f"Updated Webflow item: {status}"
    )

    return response


# ============================================================
# SYNC COLLECTION
# ============================================================

def sync_collection(
    collection_name,
    collection_id,
    articles,
    link_field,
    source_field
):

    print("")
    print(
        "======================================"
    )

    print(
        f"SYNCING {collection_name.upper()}"
    )

    print(
        "======================================"
    )

    print(
        f"Collection ID: {collection_id}"
    )


    # ========================================================
    # EXISTING ITEMS
    # ========================================================

    existing_items = get_existing_items(
        collection_id
    )


    created = 0

    updated = 0

    failed = 0


    # ========================================================
    # PROCESS ARTICLES
    # ========================================================

    for article in articles:

        title = article["title"]

        link = article["link"]

        pub_date = article["pub_date"]

        source = get_source(
            link
        )


        print("")
        print(
            "--------------------------------------"
        )

        print(
            f"Title: {title}"
        )

        print(
            f"Source: {source}"
        )

        print(
            f"Date: {pub_date}"
        )

        print(
            f"URL: {link}"
        )

        print(
            "--------------------------------------"
        )


        try:

            existing_item = (
                find_existing_article(
                    existing_items,
                    link,
                    link_field
                )
            )


            # =================================================
            # EXISTING ARTICLE
            # =================================================

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


                update_item(
                    collection_id,
                    item_id,
                    article,
                    link_field,
                    source_field
                )


                updated += 1


            # =================================================
            # NEW ARTICLE
            # =================================================

            else:

                print(
                    "New article found."
                )


                create_item(
                    collection_id,
                    article,
                    link_field,
                    source_field
                )


                created += 1


        except urllib.error.HTTPError:

            failed += 1

            print(
                "Could not sync item."
            )


    # ========================================================
    # RESULTS
    # ========================================================

    print("")

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


    return (
        created,
        updated,
        failed
    )


# ============================================================
# PUBLISH WEBFLOW
# ============================================================

def publish_site():

    print("")
    print(
        "======================================"
    )

    print(
        "PUBLISHING WEBFLOW SITE"
    )

    print(
        "======================================"
    )


    payload = {

        "publishToWebflowSubdomain":
            True
    }


    try:

        status, response = webflow_request(
            "POST",
            WEBFLOW_PUBLISH_URL,
            payload
        )


        print(
            f"Webflow publish response: {status}"
        )

        print(
            "Webflow site publish request completed."
        )


    except urllib.error.HTTPError:

        print(
            "Webflow publishing failed."
        )


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
        f"{TRENDING_NEWS_COLLECTION_ID}"
    )

    print(
        f"Site ID: {SITE_ID}"
    )


    # ========================================================
    # RSS
    # ========================================================

    rss_data = fetch_rss()


    articles = parse_rss(
        rss_data
    )


    print(
        f"Found {len(articles)} RSS articles"
    )


    if not articles:

        print(
            "No RSS articles found."
        )

        return


    # ========================================================
    # LATEST 10
    # ========================================================

    articles = articles[:10]


    print(
        "Processing latest 10 articles..."
    )


    # ========================================================
    # TICKER
    #
    # Ticker fields:
    #
    # Name          -> name
    # News URL      -> news-url
    # Source        -> source
    # Publish Date  -> publish-date
    # Slug          -> slug
    #
    # ========================================================

    sync_collection(

        collection_name="Ticker",

        collection_id=
            TICKER_COLLECTION_ID,

        articles=articles,

        link_field="news-url",

        source_field="source"
    )


    # ========================================================
    # TRENDING NEWS
    #
    # Trending News fields:
    #
    # Name          -> name
    # News Link     -> news-link
    # Source Name   -> source-name
    # Publish Date  -> publish-date
    # Slug          -> slug
    #
    # ========================================================

    sync_collection(

        collection_name="Trending News",

        collection_id=
            TRENDING_NEWS_COLLECTION_ID,

        articles=articles,

        link_field="news-link",

        source_field="source-name"
    )


    # ========================================================
    # PUBLISH
    # ========================================================

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


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
