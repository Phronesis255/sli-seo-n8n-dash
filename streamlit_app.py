# app.py
import ast
import json
import requests
import pandas as pd
import streamlit as st
from urllib.parse import urlparse, urljoin
from supabase import create_client, Client
import os
import time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup


st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")


WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook/25d396ce-f3ff-4376-996f-3e26bc73edb2s-test/25d396ce-f3ff-4376-996f-3e26bc73edb2"

username = st.secrets["username"]
password = st.secrets["password"]

# if st.button("Run workflow"):
#     with st.spinner("Triggering workflow..."):
#         try:
#             # # --- Basic Auth (most common for n8n Webhook Trigger) ---
#             # resp = requests.post(
#             #     WEBHOOK_URL,
#             #     auth=HTTPBasicAuth(username, password),
#             #     timeout=20,
#             # )

#             # --- If you actually used 'Header Auth' in n8n, use this instead:
#             resp = requests.post(
#                 WEBHOOK_URL,
#                 headers={"streamlit0": st.secrets["password"]},
#                 timeout=20,
#             )

#             status = resp.status_code
#             st.subheader(f"Response: {status}")

#             ctype = resp.headers.get("content-type", "")
#             if "application/json" in ctype:
#                 st.json(resp.json())
#             else:
#                 # Show a small text preview for non-JSON responses
#                 text = resp.text if resp.text else "(empty body)"
#                 st.code(text[:4000])  # avoid dumping huge bodies
#         except requests.RequestException as e:
#             st.error(f"Request failed: {e}")
# st.divider()
# # app.py
from supabase import create_client, Client


st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")
st.title("n8n trigger + Supabase table")

WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook/25d396ce-f3ff-4376-996f-3e26bc73edb2"

# ── n8n (Header Auth) ──────────────────────────────────────────────────────────
N8N_HEADER_NAME = "streamlit0"  # fixed per your config
N8N_HEADER_VALUE = st.secrets["password"]

# st.subheader("Trigger n8n workflow")
# if st.button("Run n8n workflow"):
#     with st.spinner("Triggering workflow..."):
#         try:
#             resp = requests.post(
#                 WEBHOOK_URL,
#                 headers={N8N_HEADER_NAME: N8N_HEADER_VALUE},
#                 timeout=20,
#             )
#             st.success(f"Webhook called (status {resp.status_code})")
#             ctype = resp.headers.get("content-type", "")
#             if "application/json" in ctype:
#                 st.json(resp.json())
#             else:
#                 st.code((resp.text or "(empty body)")[:4000])
#         except requests.RequestException as e:
#             st.error(f"Request failed: {e}")

# st.divider()
# ── Supabase setup ─────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

@st.cache_data(ttl=600, show_spinner=False)
def fetch_cache(limit: int = 200, keyword_query: str | None = None):
    q = supabase.table("Cache").select("id, keyword, fetched_at, json, AI_Summary").order("fetched_at", desc=True)
    if keyword_query:
        # ilike -> case-insensitive contains; adjust if you use a different operator
        q = q.ilike("keyword", f"%{keyword_query}%")
    res = q.limit(limit).execute()
    return res.data or []

# ── Parsing helpers ────────────────────────────────────────────────────────────
def parse_jsonish(v):
    """Try JSON first, then Python literal (handles single quotes)."""
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return json.loads(s)
        except Exception:
            pass
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            pass
    return None

def extract_domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return url or ""

def build_serp_table(serp_obj: dict, topk: int = 5) -> pd.DataFrame:
    """Return DataFrame with rank, title, domain, snippet for topk organic results."""
    rows = []
    for item in (serp_obj or {}).get("organic_results", [])[:topk]:
        rows.append({
            "rank": item.get("position"),
            "title": item.get("title"),
            "domain": extract_domain(item.get("link")),
            "snippet": item.get("snippet"),
        })
    return pd.DataFrame(rows)

def get_ai_summary_bits(ai_summary_val):
    """Return (summary_100w:str|None, top_competitor_topics:list[str]|None)."""
    obj = parse_jsonish(ai_summary_val)
    if not isinstance(obj, dict):
        return None, None
    return obj.get("summary_100w"), obj.get("top_competitor_topics")

# ── Controls ───────────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    kw = st.text_input("Filter by keyword (optional)", placeholder="e.g., prompt engineering")
with col_b:
    limit = st.slider("Max rows", 50, 1000, 200, 50)
with col_c:
    topk = st.slider("Top K organic", 3, 10, 5, 1)

if st.button("Load summaries", type="primary", use_container_width=True):
    rows = fetch_cache(limit=limit, keyword_query=kw.strip() or None)
    if not rows:
        st.info("No rows found.")
    else:
        for row in rows:
            serp = parse_jsonish(row.get("json"))
            df = build_serp_table(serp if isinstance(serp, dict) else {}, topk=topk)

            summary_100w, topics = get_ai_summary_bits(row.get("AI_Summary"))

            with st.container(border=True):
                # Header line
                st.markdown(
                    f"**Keyword:** `{row.get('keyword')}` &nbsp;&nbsp; "
                    f"**Fetched:** `{row.get('fetched_at')}` &nbsp;&nbsp; "
                    f"**ID:** `{row.get('id')}`"
                )

                # AI summary + topics
                if summary_100w or topics:
                    c1, c2 = st.columns([3, 2], vertical_alignment="top")
                    with c1:
                        if summary_100w:
                            st.markdown("**AI Summary (≈100w)**")
                            st.write(summary_100w)
                    with c2:
                        if topics:
                            st.markdown("**Top competitor topics**")
                            # Small tag-like list
                            for t in topics:
                                st.markdown(f"- {t}")
                else:
                    st.caption("No AI_Summary available for this row.")

                # SERP compact table
                if not df.empty:
                    st.markdown("**Top results (compact)**")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No organic results found in SERP payload.")

        st.success(f"Rendered {len(rows)} row(s).")

def google_custom_search(query, api_key, cse_id, num_results=10, delay=1):
    """Performs Google Custom Search with rate-limiting."""
    all_results = []
    start_index = 1
    while len(all_results) < num_results:
        remaining = num_results - len(all_results)
        current_num = min(10, remaining)
        url = "https://customsearch.googleapis.com/customsearch/v1"
        params = {
            'q': query,
            'key': api_key,
            'cx': cse_id,
            'num': current_num,
            'start': start_index,
            'hl': 'en',
            'cr': 'countryUS'
        }
        try:    
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
            if not items:
                break
            all_results.extend(items)
            start_index += current_num
            time.sleep(delay*10)  # delay between requests
        except requests.exceptions.RequestException as e:
            if response.status_code == 429:
                print("Rate limit exceeded. Retrying in 60 seconds...")
                time.sleep(120)
                continue
            else:
                print(f"Error: {e}")
                return []
    return all_results


def extract_content_from_url(url, extract_headings=False, retries=2, timeout=5):
    """Extract main textual content (paragraphs) from a webpage."""
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/58.0.3029.110 Safari/537.3'
        )
    }
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
                headings = []
                if extract_headings:
                    for level in ['h2', 'h3', 'h4']:
                        for tag in soup.find_all(level):
                            headings.append({'level': level, 'text': tag.get_text(strip=True)})

                icon_link = soup.find('link', rel=lambda x: x and ('icon' in x.lower()))
                if icon_link and icon_link.get('href'):
                    favicon_url = urljoin(url, icon_link['href'])
                else:
                    favicon_url = urljoin(url, '/favicon.ico')

                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text() for p in paragraphs])
                return title, content.strip(), favicon_url, headings, soup
        except requests.RequestException:
            pass
        time.sleep(1)
    return None, "", "", [], None

def detailed_extraction(soup, url):
    # Clone the soup to avoid modifying the original
    soup_clone = BeautifulSoup(str(soup), 'html.parser')
    
    # Remove the <footer> element and its contents so we only analyze the article content
    footer = soup_clone.find("footer")
    if footer:
        footer.decompose()
    
    # Extract Title
    title = soup_clone.title.string.strip() if soup_clone.title and soup_clone.title.string else "No Title"
    
    # Extract Meta Description
    meta_description = None
    meta_tag = soup_clone.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = meta_tag.get("content").strip()
    
    # Extract main Content (using <p> tags) and count paragraphs
    paragraphs = soup_clone.find_all("p")
    content = " ".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
    num_paragraphs = len([p for p in paragraphs if p.get_text().strip()])
    
    # Count headings and bullet lists (only those above the removed footer)
    num_h2 = len(soup_clone.find_all("h2"))
    num_h3 = len(soup_clone.find_all("h3"))
    num_bullet_lists = len(soup_clone.find_all("ul"))

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "content": content,
        "num_paragraphs": num_paragraphs,
        "num_h2": num_h2,
        "num_h3": num_h3,
        "num_bullet_lists": num_bullet_lists
    }

@st.cache_resource
def lemmatize_text(text: str) -> str:
    doc = nlp(text)
    lemmatized_tokens = []
    for token in doc:
        # context-aware overrides
        if token.text.lower() == "media" and token.lemma_.lower() == "medium":
            lemmatized_tokens.append("media")
        elif token.text.lower() == "data" and token.lemma_.lower() == "datum":
            lemmatized_tokens.append("data")
        elif token.text.lower() == "publishers" and token.lemma_.lower() == "publisher":
            lemmatized_tokens.append("publisher")
        else:
            lemmatized_tokens.append(token.lemma_)
    return ' '.join(lemmatized_tokens)


def remove_duplicate_questions(questions, similarity_threshold=0.75):
    # If 0 or 1 questions, there's nothing to deduplicate
    if len(questions) < 2:
        return questions

    # Preprocess questions
    def preprocess(text):
        # Lowercase, remove punctuation
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        return text

    # Encode questions using SentenceTransformer
    model = load_embedding_model()
    preprocessed = [preprocess(q) for q in questions]
    embeddings = model.encode(preprocessed)

    # If embeddings is empty or only 1 row, again just return
    if embeddings.shape[0] < 2:
        return questions

    # Compute cosine similarity matrix
    similarity_matrix = cosine_similarity(embeddings)

    # Cluster questions
    clustering_model = AgglomerativeClustering(
        n_clusters=None,
        affinity='precomputed',
        linkage='complete',
        distance_threshold=1 - similarity_threshold
    )
    clustering_model.fit(1 - similarity_matrix)

    # Select a representative question from each cluster
    cluster_labels = clustering_model.labels_
    cluster_map = {}
    for idx, label in enumerate(cluster_labels):
        cluster_map.setdefault(label, []).append(questions[idx])

    final_questions = []
    for _, qs in cluster_map.items():
        # pick the shortest question from the cluster
        rep = min(qs, key=len)
        final_questions.append(rep)

    return final_questions


def extract_brand_name(url, title):
    parsed = urlparse(url)
    parts = parsed.netloc.split('.')
    if parts and parts[0] == 'www':
        parts.pop(0)
    domain_root = parts[0].capitalize() if parts else 'Unknown'

    if title:
        segs = title.split(' - ')
        for seg in reversed(segs):
            ratio = difflib.SequenceMatcher(None, domain_root.lower(), seg.lower()).ratio()
            if ratio > 0.8:
                return seg.strip()
    return domain_root

@st.cache_resource
def is_brand_mentioned(term, brand_name):
    # direct substring
    if brand_name.lower() in term.lower():
        return True
    # fuzzy match ratio
    ratio = difflib.SequenceMatcher(
        None,
        term.lower().replace(' ', ''),
        brand_name.lower().replace(' ', '')
    ).ratio()
    if ratio > 0.8:
        return True
    # check for named entity
    doc = nlp(term)
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'PRODUCT', 'PERSON', 'GPE']:
            ratio_ent = difflib.SequenceMatcher(
                None,
                ent.text.lower().replace(' ', ''),
                brand_name.lower().replace(' ', '')
            ).ratio()
            if ratio_ent > 0.8:
                return True
    return False


def is_not_branded(question):
    """Return True if question does NOT mention any brand in st.session_state['brands']"""
    brands = st.session_state.get('brands', [])
    for brand in brands:
        if is_brand_mentioned(question, brand):
            return False
    return True

# Initialize sentiment pipeline (cache as needed)
sentiment_pipeline = pipeline(
    "sentiment-analysis", 
    model="distilbert-base-uncased-finetuned-sst-2-english"
)

def compute_readability(text):
    if not text or len(text.split()) < 3:
        return None
    try:
        return textstat.flesch_kincaid_grade(text)
    except Exception:
        return None

def compute_sentiment(text):
    text = text.strip()
    if not text:
        return None
    try:
        # If text is very long, limit to first 512 characters
        trimmed_text = text if len(text) <= 512 else text[:512]
        result = sentiment_pipeline(trimmed_text)
        if result:
            label = result[0]['label'].upper()
            score = result[0]['score']
            return score if label == "POSITIVE" else -score
        else:
            return None
    except Exception:
        return None
def compute_pos_counts(text, normalize=True):
    """Count the number of adverbs, adjectives, and verbs in the given text.
    
    Args:
        text (str): The input text to analyze.
        normalize (bool): Whether to return normalized counts. Defaults to True.
    
    Returns:
        dict: A dictionary with counts of adverbs, adjectives, and verbs.
    """
    doc = nlp(text)
    total_words = len([token for token in doc if token.is_alpha])  # Exclude punctuation

    pos_counts = {
        "adverbs": sum(1 for token in doc if token.pos_ == "ADV"),
        "adjectives": sum(1 for token in doc if token.pos_ == "ADJ"),
        "verbs": sum(1 for token in doc if token.pos_ == "VERB")
    }

    if normalize and total_words > 0:
        for key in pos_counts:
            pos_counts[key] /= total_words  # Normalize each POS count
    elif normalize:
        for key in pos_counts:
            pos_counts[key] = 0  # Avoid division by zero

    return pos_counts


def compute_serp_features(details, position):
    content = details.get("content", "")
    pos_counts = compute_pos_counts(content)  # Get POS counts

    features = {
        "position": position,
        "url": details.get("url"),
        "title": details.get("title"),
        "title_readability": compute_readability(details.get("title")),
        "title_sentiment": compute_sentiment(details.get("title")),
        "meta_readability": compute_readability(details.get("meta_description") or ""),
        "meta_sentiment": compute_sentiment(details.get("meta_description") or ""),
        "content_readability": compute_readability(details.get("content")),
        "content_sentiment": compute_sentiment(details.get("content")),
        "word_count": len(details.get("content", "").split()),
        "num_paragraphs": details.get("num_paragraphs"),
        "num_h2": details.get("num_h2"),
        "num_h3": details.get("num_h3"),
        "num_bullet_lists": details.get("num_bullet_lists"),
        "entity_count": compute_ner_count(content),
        "lexical_diversity": compute_lexical_diversity(content),
        "adverbs": pos_counts["adverbs"],
        "adjectives": pos_counts["adjectives"],
        "verbs": pos_counts["verbs"]
    }
    return features


# ── Keyword Research Workflow ─────────────────────────────────────────────────
def perform_analysis(keyword):
    max_contents = 20
    """Refactored function using logic consistent with the React+FastAPI version,
       but preserving EXACT st.session_state keys and formats used in the original code.
    """
    if 'words_to_check' not in st.session_state:
        st.session_state['words_to_check'] = []

    start_time = time.time()
    user_email = st.session_state.get("username", "guest")  # or "user_id" if you have it

    status_placeholder = st.empty()  # Create a placeholder for dynamic updates
    status_placeholder.info('Retrieving top search results...')
    st.write(f"Keyword: {keyword}")

    st.session_state['keyword'] = keyword
    st.session_state['serp_contents'] = []  # NEW: store structured data

    api_key = os.getenv("API_KEY")
    cse_id = os.getenv("CSE_ID")
    st.write(f"API Key: {api_key}, CSE ID: {cse_id}")

    # 1) Retrieve search items
    results = google_custom_search(keyword, api_key, cse_id, num_results=35)
    st.write(f"Search results: {results}")
    if not results:
        status_placeholder.error('No results found.')
        return

    top_urls = [item['link'] for item in results if 'link' in item]
    st.write(f"Top URLs: {top_urls}")
    if not top_urls:
        status_placeholder.error('No URLs found.')
        return
    st.session_state['top_urls'] = top_urls

    # 2) Extract content from top URLs
    titles, favicons, retrieved_content = [], [], []
    headings_data = []
    successful_urls = []
    word_counts = []
    brand_names = set()

    progress = st.progress(0)
    for idx, url in enumerate(top_urls):
        if len(retrieved_content) >= max_contents:
            break
        print(f"\nProcessing URL {idx+1}/{len(top_urls)}: {url}")
        progress.progress(idx / len(top_urls))
        status_placeholder.info(f"Retrieving content from {url}...")
        t, content, favicon_url, heads, soup = extract_content_from_url(url, extract_headings=True)
        st.write(f"URL: {url}, Title: {t}, Content Length: {len(content) if content else 0}")
        if t is None:
            t = "No Title"

        # brand
        print("Filtering branded content")
        brand_name = extract_brand_name(url, t)
        brand_names.add(brand_name)

        if heads:
            for h in heads:
                if 'text' in h:
                    headings_data.append({
                        'text': h['text'].strip(),
                        'url': url,
                        'title': t
                    })

        if content:
            wc = len(content.split())
            retrieved_content.append(content)
            successful_urls.append(url)
            titles.append(t)
            favicons.append(favicon_url)
            # anchor word count at least 1000
            word_counts.append(wc if wc > 1000 else 1000)
            st.session_state['serp_contents'].append({
                "position": idx + 1,      # 1-based SERP rank
                "url": url,
                "title": t,
                "content": content,
                "favicon": favicon_url,
                "word_counts": wc if wc > 1000 else 1000,
                "soup": soup
            })
        time.sleep(0.5)
    st.session_state['successful_urls'] = successful_urls
    progress.empty()
    status_placeholder.empty()  # Remove the last message after completion
    st.write(f"Retrieved Content: {retrieved_content}")
    st.write(f"Successful URLs: {successful_urls}")
    st.write(f"Brand Names: {brand_names}")

    # store brand names
    st.session_state['brands'] = list(brand_names)

    if not retrieved_content:
        st.error('Failed to retrieve sufficient content.')
        return

    if len(word_counts) > 0:
        ideal_count = int(np.median(word_counts)) + 500
    else:
        ideal_count = 1000
    st.session_state['ideal_word_count'] = ideal_count
    st.write(f"Ideal Word Count: {ideal_count}")

    # 3) Clean and lemmatize
    docs_lemmatized = retrieved_content #[lemmatize_text(doc) for doc in retrieved_content]
    st.write(f"Lemmatized Documents: {docs_lemmatized}")

    # 5) Display top search results
    st.subheader('Top Search Results')
    for i in range(len(titles)):
        fc = favicons[i]
        t = titles[i]
        link = successful_urls[i]
        wc = word_counts[i]
        st.markdown(
            f"""
            <div style="background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; color: black;">
                <div style="display: flex; align-items: center;">
                    <img src="{fc}" width="32" style="margin-right: 10px;">
                    <div>
                        <strong>{t}</strong> ({wc} words)<br>
                        <a href="{link}" target="_blank">{link}</a>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True
        )

    lower_bound = (ideal_count // 500) * 500
    upper_bound = lower_bound + 500
    st.success(f"**Suggested Word Count:** Aim for approx. {lower_bound}–{upper_bound} words based on top content.")

    print("Starting TF-IDF operations")

    # 6) TF-IDF + CountVectorizer
    model = load_embedding_model()
    tfidf_vectorizer = TfidfVectorizer(ngram_range=(1,3))
    tf_vectorizer    = CountVectorizer(ngram_range=(1,3))

    tfidf_matrix = tfidf_vectorizer.fit_transform(docs_lemmatized).toarray()
    tf_matrix    = tf_vectorizer.fit_transform(docs_lemmatized).toarray()

    feature_names = tfidf_vectorizer.get_feature_names_out()
    filtered_feats = filter_terms(feature_names)
    st.write(f"Filtered Features: {filtered_feats}")

    # filter the matrices
    idxs = [i for i, term in enumerate(feature_names) if term in filtered_feats]
    tfidf_matrix_f = tfidf_matrix[:, idxs]
    tf_matrix_f    = tf_matrix[:, idxs]
    filtered_feature_names = [feature_names[i] for i in idxs]

    # compute average
    avg_tfidf = np.mean(tfidf_matrix_f, axis=0)
    avg_tf    = np.mean(tf_matrix_f, axis=0)
    # also track doc lengths
    doc_word_counts = [len(d.split()) for d in docs_lemmatized]
    avg_doc_len = float(sum(doc_word_counts)) / max(1, len(doc_word_counts))

    # normalizing
    avg_tfidf /= avg_doc_len
    avg_tf    /= avg_doc_len

    print("Generating embeddings...")
    st.info("Indexing results... Generating embeddings...")
    # 7) Now compute similarity for each term to the user keyword
    keyword_emb = model.encode([keyword])[0]
    term_embeddings = model.encode(filtered_feature_names)
    similarities = cosine_similarity([keyword_emb], term_embeddings)[0]

    # "Combined Score" = average tf-idf * similarity
    combined_scores = avg_tfidf * similarities

    # get top 50
    N = 50
    top_idx = np.argsort(combined_scores)[-N:][::-1]
    top_terms = [filtered_feature_names[i] for i in top_idx]
    top_combined = [combined_scores[i] for i in top_idx]
    top_tfidf    = [avg_tfidf[i] for i in top_idx]
    top_tf       = [avg_tf[i] for i in top_idx]
    top_sim      = [similarities[i] for i in top_idx]

    st.write(f"Top Terms: {top_terms}")
    st.write(f"Top Combined Scores: {top_combined}")
    st.write(f"Top TF-IDF Scores: {top_tfidf}")
    st.write(f"Top TF Scores: {top_tf}")
    st.write(f"Top Similarities: {top_sim}")

    # 8) Store in session_state
    st.session_state['chart_data'] = pd.DataFrame({
        'Terms': top_terms,
        'Combined Score': top_combined,
        'Average TF-IDF Score': [x * 100 for x in top_tfidf],
        'Similarity to Keyword': [x * 100 for x in top_sim]
    })

    st.session_state['words_to_check'] = [
        {
            'Term': top_terms[i],
            'Average TF Score': top_tf[i],
            'Average TF-IDF Score': top_tfidf[i]
        }
        for i in range(len(top_terms))
    ]

    st.session_state['analysis_completed'] = True

    elapsed_time = time.time() - start_time
    print(f"Time taken for analysis: {elapsed_time:.2f} seconds")
    st.write(f"Time taken for analysis: {elapsed_time:.2f} seconds")

st.divider()
st.subheader("Keyword Research Workflow")
keyword = st.text_input("Enter a keyword for analysis", placeholder="e.g., AI tools")

if st.button("Analyze Keyword"):
    if keyword.strip():
        perform_analysis(keyword.strip())
    else:
        st.error("Please enter a valid keyword.")

# Display analysis results if available
