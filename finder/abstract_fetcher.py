import re
import time
import requests

def clean_text(text):
    if not text:
        return ""
    text = text.replace('{', '').replace('}', '').replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def clean_latex_title(title):
    if not title:
        return ""
    # Strip LaTeX commands like \textit{...}, keeping the interior text
    title = re.sub(r'\\\w+{(.*?)}', r'\1', title)
    # Strip curly braces
    title = title.replace('{', '').replace('}', '')
    # Strip backslashes (turning \beta to beta)
    title = title.replace('\\', '')
    # Strip math mode delimiters ($)
    title = title.replace('$', '')
    # Normalize whitespaces and newlines
    title = title.replace('\n', ' ')
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def clean_crossref_abstract(raw):
    """
    Crossref wraps abstracts in JATS XML, e.g. <jats:p>...</jats:p>,
    sometimes with nested tags and a leading 'Abstract' label. Strip tags
    and normalize whitespace.
    """
    if not raw:
        return None
    text = re.sub(r'<[^>]+>', ' ', raw)  # strip all XML/HTML tags
    text = re.sub(r'\s+', ' ', text).strip()
    # Crossref often prefixes the literal word "Abstract"
    text = re.sub(r'^Abstract\.?\s*', '', text, flags=re.IGNORECASE)
    return text if text else None

def api_get(url, params=None, headers=None, max_retries=2, log_callback=None):
    """
    Wraps requests.get with retry-on-429 and logging.
    Returns (status_code, json_or_none, error_message_or_none)
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=3)
        except requests.exceptions.RequestException as e:
            return None, None, f"Network error: {e}"

        if resp.status_code == 200:
            try:
                return 200, resp.json(), None
            except ValueError:
                return 200, None, "200 OK but response was not valid JSON"

        if resp.status_code == 429:
            wait = 5 * attempt
            msg = f"      [429 rate-limited] retrying in {wait}s (attempt {attempt}/{max_retries})..."
            if log_callback:
                log_callback(msg)
            time.sleep(wait)
            continue

        return resp.status_code, None, f"HTTP {resp.status_code}: {resp.text[:200]}"

    return 429, None, "Gave up after repeated 429 rate-limiting"

def fetch_paper_by_id(paper_id, log, headers, max_retries=4, log_callback=None):
    fields = "title,abstract,tldr,externalIds"
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    status, data, err = api_get(url, params={"fields": fields}, headers=headers, max_retries=max_retries, log_callback=log_callback)
    if err:
        log.append(f"  -> full-record lookup error: {err}")
        return None
    if data:
        abstract = data.get('abstract')
        if not abstract and data.get('tldr') and data['tldr'].get('text'):
            abstract = "[TLDR] " + data['tldr']['text']
        doi = data.get('externalIds', {}).get('DOI')
        return {"abstract": abstract, "doi": doi}
    return None

def reconstruct_openalex_abstract(inverted_index):
    if not inverted_index:
        return None
    position_map = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_map[pos] = word
    if not position_map:
        return None
    ordered = [position_map[i] for i in sorted(position_map.keys())]
    return " ".join(ordered)

def fetch_from_openalex(doi, title, log, mailto, max_retries=4, log_callback=None):
    params_common = {"mailto": mailto} if mailto else {}

    if doi:
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        status, data, err = api_get(url, params=params_common, headers=None, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"OpenAlex DOI lookup error: {err}")
        elif data:
            abstract = reconstruct_openalex_abstract(data.get('abstract_inverted_index'))
            res_doi = data.get('doi')
            resolved_doi = res_doi.replace("https://doi.org/", "").strip() if res_doi else doi
            if abstract:
                return {"abstract": abstract, "doi": resolved_doi}
            log.append("OpenAlex DOI matched but no abstract_inverted_index present")
    elif title:
        url = "https://api.openalex.org/works"
        params = {**params_common, "search": title, "per_page": 1}
        status, data, err = api_get(url, params=params, headers=None, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"OpenAlex title search error: {err}")
        elif data:
            results = data.get('results', [])
            if results:
                abstract = reconstruct_openalex_abstract(results[0].get('abstract_inverted_index'))
                res_doi = results[0].get('doi')
                resolved_doi = res_doi.replace("https://doi.org/", "").strip() if res_doi else None
                if abstract:
                    return {"abstract": abstract, "doi": resolved_doi}
                log.append("OpenAlex title search found a record but no abstract_inverted_index")
            else:
                log.append("OpenAlex title search returned no candidates")

    return None

def fetch_from_core(doi, title, log, api_key, max_retries=4, log_callback=None):
    if not api_key:
        return None
    headers = {"Authorization": f"Bearer {api_key}"}
    if doi:
        url = "https://api.core.ac.uk/v3/search/works"
        params = {"q": f'doi:"{doi}"', "limit": 1}
        status, data, err = api_get(url, params=params, headers=headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"CORE DOI search error: {err}")
        elif data:
            results = data.get('results', [])
            if results and results[0].get('abstract'):
                res_doi = results[0].get('doi')
                return {"abstract": clean_text(results[0]['abstract']), "doi": res_doi or doi}
            if results:
                log.append("CORE DOI matched but record has no abstract field")
            else:
                log.append("CORE DOI search returned no candidates")
    elif title:
        url = "https://api.core.ac.uk/v3/search/works"
        params = {"q": f'title:"{title}"', "limit": 1}
        status, data, err = api_get(url, params=params, headers=headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"CORE title search error: {err}")
        elif data:
            results = data.get('results', [])
            if results and results[0].get('abstract'):
                res_doi = results[0].get('doi')
                return {"abstract": clean_text(results[0]['abstract']), "doi": res_doi}
            if results:
                log.append("CORE title search found a record but no abstract field")
            else:
                log.append("CORE title search returned no candidates")

    return None

def fetch_from_crossref(doi, title, log, mailto, max_retries=4, log_callback=None):
    headers = {"User-Agent": f"abstract-backfill-script (mailto:{mailto})"} if mailto else {}
    if doi:
        url = f"https://api.crossref.org/works/{doi}"
        status, data, err = api_get(url, params=None, headers=headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"Crossref DOI lookup error: {err}")
        elif data:
            msg = data.get('message', {})
            abstract = clean_crossref_abstract(msg.get('abstract'))
            res_doi = msg.get('DOI')
            if abstract:
                return {"abstract": abstract, "doi": res_doi or doi}
            log.append("Crossref DOI matched but record has no abstract field")
    elif title:
        url = "https://api.crossref.org/works"
        params = {"query.bibliographic": title, "rows": 1}
        status, data, err = api_get(url, params=params, headers=headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"Crossref title search error: {err}")
        elif data:
            items = data.get('message', {}).get('items', [])
            if items:
                top = items[0]
                abstract = clean_crossref_abstract(top.get('abstract'))
                res_doi = top.get('DOI')
                if abstract:
                    return {"abstract": abstract, "doi": res_doi}
                log.append("Crossref title search found a record but it has no abstract field")
            else:
                log.append("Crossref title search returned no candidates")

    return None

def fetch_full_abstract(doi, title, config, log_callback=None):
    """
    Tries to retrieve the abstract and resolved DOI of a paper from OpenAlex, Crossref, CORE, and Semantic Scholar.
    Returns: (abstract, resolved_doi, source, log)
    """
    doi = clean_text(doi)
    title = clean_latex_title(title)
    log = []

    s2_headers = {"x-api-key": config.get('semantic_scholar_api_key')} if config.get('semantic_scholar_api_key') else {}
    max_retries = config.get('max_retries', 2)

    # Priority 1: OpenAlex
    oa_res = fetch_from_openalex(doi, title, log, config.get('openalex_mailto'), max_retries, log_callback)
    if oa_res:
        if oa_res.get('abstract'):
            return oa_res['abstract'], oa_res.get('doi') or doi, "OpenAlex", log
        if oa_res.get('doi') and not doi:
            doi = oa_res['doi']
            if log_callback:
                log_callback(f"      [info] OpenAlex resolved DOI: {doi}. Switching to exact DOI queries.")

    # Priority 2: Crossref
    cr_res = fetch_from_crossref(doi, title, log, config.get('crossref_mailto'), max_retries, log_callback)
    if cr_res:
        if cr_res.get('abstract'):
            return cr_res['abstract'], cr_res.get('doi') or doi, "Crossref", log
        if cr_res.get('doi') and not doi:
            doi = cr_res['doi']
            if log_callback:
                log_callback(f"      [info] Crossref resolved DOI: {doi}. Switching to exact DOI queries.")

    # Priority 3: CORE
    core_key = config.get('core_api_key')
    if core_key:
        core_res = fetch_from_core(doi, title, log, core_key, max_retries, log_callback)
        if core_res:
            if core_res.get('abstract'):
                return core_res['abstract'], core_res.get('doi') or doi, "CORE", log
            if core_res.get('doi') and not doi:
                doi = core_res['doi']
                if log_callback:
                    log_callback(f"      [info] CORE resolved DOI: {doi}. Switching to exact DOI queries.")

    # Priority 4: Semantic Scholar
    fields = "title,abstract,tldr,paperId,externalIds"

    if doi:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        status, data, err = api_get(url, params={"fields": fields}, headers=s2_headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"DOI lookup error: {err}")
        elif data:
            res_doi = data.get('externalIds', {}).get('DOI') or doi
            if data.get('abstract'):
                return data['abstract'], res_doi, "Semantic Scholar (DOI)", log
            if data.get('tldr') and data['tldr'].get('text'):
                return "[TLDR] " + data['tldr']['text'], res_doi, "Semantic Scholar (DOI, TLDR)", log
            log.append("DOI matched but search-projection had no abstract/tldr")
            if data.get('paperId'):
                time.sleep(1.0)
                result = fetch_paper_by_id(data['paperId'], log, s2_headers, max_retries, log_callback)
                if result and result.get('abstract'):
                    return result['abstract'], result.get('doi') or res_doi, "Semantic Scholar (DOI -> full record)", log

    elif title:
        match_url = "https://api.semanticscholar.org/graph/v1/paper/search/match"
        status, data, err = api_get(match_url, params={"query": title, "fields": fields}, headers=s2_headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"/match error: {err}")
        elif data and data.get('data'):
            paper = data['data'][0]
            res_doi = paper.get('externalIds', {}).get('DOI')
            if paper.get('abstract'):
                return paper['abstract'], res_doi, "Semantic Scholar (match)", log
            if paper.get('tldr') and paper['tldr'].get('text'):
                return "[TLDR] " + paper['tldr']['text'], res_doi, "Semantic Scholar (match, TLDR)", log
            log.append("/match found paper but search-projection had no abstract/tldr")
            if paper.get('paperId'):
                time.sleep(1.0)
                result = fetch_paper_by_id(paper['paperId'], log, s2_headers, max_retries, log_callback)
                if result and result.get('abstract'):
                    return result['abstract'], result.get('doi') or res_doi, "Semantic Scholar (match -> full record)", log
        else:
            log.append("/match returned no candidates")

        time.sleep(1.0)

        search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        status, data, err = api_get(search_url, params={"query": title, "limit": 1, "fields": fields}, headers=s2_headers, max_retries=max_retries, log_callback=log_callback)
        if err:
            log.append(f"/search error: {err}")
        elif data and data.get('data'):
            paper = data['data'][0]
            res_doi = paper.get('externalIds', {}).get('DOI')
            if paper.get('abstract'):
                return paper['abstract'], res_doi, "Semantic Scholar (search)", log
            if paper.get('tldr') and paper['tldr'].get('text'):
                return "[TLDR] " + paper['tldr']['text'], res_doi, "Semantic Scholar (search, TLDR)", log
            log.append("/search found paper but search-projection had no abstract/tldr")
            if paper.get('paperId'):
                time.sleep(1.0)
                result = fetch_paper_by_id(paper['paperId'], log, s2_headers, max_retries, log_callback)
                if result and result.get('abstract'):
                    return result['abstract'], result.get('doi') or res_doi, "Semantic Scholar (search -> full record)", log
        else:
            log.append("/search returned no candidates")

    return None, None, None, log
