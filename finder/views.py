import io
import json
import re
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from finder.task_manager import TaskManager, is_incomplete_abstract

def parse_ris(content):
    entries = []
    current_entry = {}
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = re.match(r'^([A-Z0-9]{2})\s*-\s*(.*)$', line)
        if match:
            tag, val = match.groups()
            tag = tag.upper()
            val = val.strip()
            
            if tag == 'TY':
                if current_entry:
                    entries.append(current_entry)
                val_upper = val.upper()
                if val_upper in ['JOUR', 'MGZN', 'NEWS']:
                    bib_type = 'article'
                elif val_upper in ['BOOK', 'CHAP']:
                    bib_type = 'book'
                elif val_upper == 'CONF':
                    bib_type = 'inproceedings'
                else:
                    bib_type = val.lower()
                current_entry = {'ENTRYTYPE': bib_type}
            elif tag == 'ER':
                if current_entry:
                    entries.append(current_entry)
                    current_entry = {}
            elif current_entry is not None:
                if tag in ['TI', 'T1', 'CT']:
                    current_entry['title'] = val
                elif tag == 'AU':
                    if 'author' in current_entry:
                        current_entry['author'] += " and " + val
                    else:
                        current_entry['author'] = val
                elif tag in ['JO', 'JF', 'T2', 'JA']:
                    current_entry['journal'] = val
                elif tag in ['PY', 'Y1']:
                    year_match = re.search(r'\b\d{4}\b', val)
                    current_entry['year'] = year_match.group(0) if year_match else val
                elif tag in ['DO', 'DI']:
                    current_entry['doi'] = val
                elif tag in ['AB', 'N2']:
                    if 'abstract' in current_entry:
                        current_entry['abstract'] += " " + val
                    else:
                        current_entry['abstract'] = val
                elif tag in ['ID', 'UR', 'L2']:
                    if tag == 'ID':
                        current_entry['ID'] = val
                    elif tag == 'UR':
                        current_entry['url'] = val
                else:
                    current_entry[tag] = val
        else:
            if current_entry and 'abstract' in current_entry and line:
                current_entry['abstract'] += " " + line
                
    if current_entry and current_entry not in entries:
        entries.append(current_entry)
        
    for idx, entry in enumerate(entries, 1):
        if 'ID' not in entry or not entry['ID']:
            entry['ID'] = f"paper_{idx}"
        if 'ENTRYTYPE' not in entry:
            entry['ENTRYTYPE'] = 'journal'
            
    return entries

def serialize_to_ris(entries):
    output = []
    for entry in entries:
        output.append("TY  - JOUR")
        if 'ID' in entry:
            output.append(f"ID  - {entry['ID']}")
        if 'title' in entry:
            output.append(f"TI  - {entry['title']}")
        if 'author' in entry:
            authors = entry['author'].split(' and ')
            for author in authors:
                output.append(f"AU  - {author.strip()}")
        if 'journal' in entry:
            output.append(f"JO  - {entry['journal']}")
        if 'year' in entry:
            output.append(f"PY  - {entry['year']}")
        if 'doi' in entry:
            output.append(f"DO  - {entry['doi']}")
        if 'url' in entry:
            output.append(f"UR  - {entry['url']}")
        if 'abstract' in entry:
            output.append(f"AB  - {entry['abstract']}")
        if 'abstract_source' in entry:
            output.append(f"N1  - Abstract source: {entry['abstract_source']}")
            
        for key, val in entry.items():
            if len(key) == 2 and key.isupper() and key not in ['TY', 'ER', 'TI', 'AU', 'JO', 'PY', 'DO', 'UR', 'AB', 'ID']:
                output.append(f"{key}  - {val}")
                
        output.append("ER  - ")
        output.append("")
        
    return "\n".join(output)

def dashboard_view(request):
    # Pre-populate empty configurations so the user must provide their own
    context = {
        "default_config": {
            "semantic_scholar_api_key": "",
            "crossref_mailto": "",
            "openalex_mailto": "",
            "core_api_key": "",
            "sleep_seconds": 1.0,
            "max_retries": 4
        }
    }
    return render(request, "finder/dashboard.html", context)

@require_POST
def upload_bib(request):
    if 'file' not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)
    
    file = request.FILES['file']
    if not any(file.name.endswith(ext) for ext in ['.bib', '.bibtex', '.csv', '.ris']):
        return JsonResponse({"error": "Only .bib, .bibtex, .csv, or .ris files are supported"}, status=400)
        
    try:
        content = file.read().decode('utf-8')
        if file.name.endswith('.csv'):
            import csv
            from bibtexparser.bibdatabase import BibDatabase
            
            # Parse CSV
            reader = csv.DictReader(io.StringIO(content))
            entries = []
            
            for row in reader:
                entry = {}
                for key, val in row.items():
                    if not key:
                        continue
                    k_lower = key.strip().lower()
                    val_str = val.strip() if val else ""
                    
                    if k_lower in ['id', 'key', 'citation key', 'bibtexkey', 'paper id']:
                        entry['ID'] = val_str
                    elif k_lower in ['title', 'paper title']:
                        entry['title'] = val_str
                    elif k_lower in ['author', 'authors', 'author(s)']:
                        entry['author'] = val_str
                    elif k_lower in ['journal', 'booktitle', 'venue', 'journal/booktitle', 'publication']:
                        entry['journal'] = val_str
                    elif k_lower in ['year', 'date', 'pub year']:
                        entry['year'] = val_str
                    elif k_lower in ['doi', 'link']:
                        entry['doi'] = val_str
                    elif k_lower in ['abstract', 'summary', 'tldr']:
                        entry['abstract'] = val_str
                    elif k_lower in ['abstract_source', 'source', 'abstract source']:
                        entry['abstract_source'] = val_str
                    else:
                        entry[key.strip()] = val_str
                
                # Default ENTRYTYPE and ID if missing
                if 'ID' not in entry or not entry['ID']:
                    entry['ID'] = f"paper_{len(entries) + 1}"
                if 'ENTRYTYPE' not in entry:
                    entry['ENTRYTYPE'] = 'article'
                    
                # Only append if title, DOI, or ID exists
                if entry.get('title') or entry.get('doi') or entry.get('ID'):
                    entries.append(entry)
            
            bib_database = BibDatabase()
            bib_database.entries = entries
        elif file.name.endswith('.ris'):
            from bibtexparser.bibdatabase import BibDatabase
            entries = parse_ris(content)
            bib_database = BibDatabase()
            bib_database.entries = entries
        else:
            # Use parser with convert_to_unicode to resolve LaTeX special characters
            parser = BibTexParser()
            parser.customization = convert_to_unicode
            bib_database = bibtexparser.loads(content, parser=parser)
    except Exception as e:
        return JsonResponse({"error": f"Failed to parse file: {str(e)}"}, status=400)
    
    if not bib_database.entries:
        return JsonResponse({"error": "The uploaded file contains no valid entries"}, status=400)
        
    # Extract settings from POST parameters
    sleep_seconds = 1.0
    try:
        sleep_seconds = float(request.POST.get('sleep_seconds', 1.0))
    except ValueError:
        pass
        
    max_retries = 4
    try:
        max_retries = int(request.POST.get('max_retries', 4))
    except ValueError:
        pass

    config = {
        "semantic_scholar_api_key": request.POST.get('semantic_scholar_api_key', '').strip(),
        "crossref_mailto": request.POST.get('crossref_mailto', '').strip(),
        "openalex_mailto": request.POST.get('openalex_mailto', '').strip(),
        "core_api_key": request.POST.get('core_api_key', '').strip(),
        "sleep_seconds": sleep_seconds,
        "max_retries": max_retries,
    }
    
    # Start task
    task_id = TaskManager.create_task(bib_database, file.name, config)
    return JsonResponse({"task_id": task_id})

def task_status(request, task_id):
    task = TaskManager.get_task(task_id)
    if not task:
        return JsonResponse({"error": "Task not found"}, status=404)
    return JsonResponse(task.to_dict())

@require_POST
def cancel_task(request, task_id):
    success = TaskManager.cancel_task(task_id)
    if not success:
        return JsonResponse({"error": "Task not found"}, status=404)
    return JsonResponse({"status": "success"})

def task_preview(request, task_id):
    task = TaskManager.get_task(task_id)
    if not task:
        return JsonResponse({"error": "Task not found"}, status=404)
        
    search_query = request.GET.get('search', '').lower()
    status_filter = request.GET.get('status', 'all')  # all, fetched, missing, existing, edited
    
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    
    filtered_entries = []
    
    with task.lock:
        for entry in task.bib_database.entries:
            eid = entry.get('ID', '')
            title = entry.get('title', '')
            doi = entry.get('doi', '')
            abstract = entry.get('abstract', '')
            source = entry.get('abstract_source', '')
            
            # Compute status
            if not abstract:
                status = "missing"
            elif is_incomplete_abstract(abstract):
                status = "incomplete"
            elif source == "Pre-existing":
                status = "existing"
            elif source == "Manually Edited":
                status = "edited"
            else:
                status = "fetched"
                
            # Apply status filter
            if status_filter != 'all' and status != status_filter:
                continue
                
            # Apply search filter
            if search_query:
                authors = entry.get('author', '')
                if (search_query not in eid.lower() and 
                    search_query not in title.lower() and 
                    search_query not in doi.lower() and 
                    search_query not in authors.lower()):
                    continue
            
            # Compute a quick 1-sentence summary (TLDR)
            tldr = ""
            if abstract:
                if abstract.startswith("[TLDR]"):
                    tldr = abstract.replace("[TLDR]", "").strip()
                else:
                    sentences = [s.strip() for s in abstract.split('.') if s.strip()]
                    if sentences:
                        tldr_cand = sentences[0].strip()
                        if len(tldr_cand) < 40 and len(sentences) > 1:
                            tldr_cand += ". " + sentences[1].strip()
                        if tldr_cand and not tldr_cand.endswith('.'):
                            tldr_cand += "."
                        tldr = tldr_cand
            
            # Map entry info for frontend preview
            filtered_entries.append({
                "id": eid,
                "title": title,
                "author": entry.get('author', 'Unknown'),
                "journal": entry.get('journal', entry.get('booktitle', 'N/A')),
                "year": entry.get('year', 'N/A'),
                "doi": doi,
                "abstract": abstract,
                "abstract_source": source,
                "status": status,
                "tldr": tldr
            })
            
    # Paginate
    total_count = len(filtered_entries)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = filtered_entries[start_idx:end_idx]
    
    return JsonResponse({
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "entries": paginated
    })

@require_POST
def update_entry(request, task_id):
    task = TaskManager.get_task(task_id)
    if not task:
        return JsonResponse({"error": "Task not found"}, status=404)
        
    try:
        data = json.loads(request.body)
        entry_id = data.get('entry_id')
        new_abstract = data.get('abstract', '').strip()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)
        
    if not entry_id:
        return JsonResponse({"error": "entry_id is required"}, status=400)
        
    with task.lock:
        found = False
        for entry in task.bib_database.entries:
            if entry.get('ID') == entry_id:
                found = True
                old_abstract = entry.get('abstract', '')
                old_source = entry.get('abstract_source', '')
                
                if new_abstract:
                    entry['abstract'] = new_abstract
                    entry['abstract_source'] = "Manually Edited"
                else:
                    entry.pop('abstract', None)
                    entry.pop('abstract_source', None)
                
                # Recalculate stats based on transition
                # Old state
                was_missing = not old_abstract or is_incomplete_abstract(old_abstract)
                was_existing = old_abstract and not is_incomplete_abstract(old_abstract) and old_source == "Pre-existing"
                was_fetched = old_abstract and not is_incomplete_abstract(old_abstract) and old_source not in ("", "Pre-existing", "Manually Edited")
                was_edited = old_source == "Manually Edited"
                
                # New state
                is_missing = not new_abstract
                is_existing = False # editing overrides to manually edited
                is_fetched = False
                is_edited = bool(new_abstract) and not is_incomplete_abstract(new_abstract)
                is_incomplete = bool(new_abstract) and is_incomplete_abstract(new_abstract)
                
                # Adjust counts
                # Subtract old state
                if was_existing:
                    task.existing_count = max(0, task.existing_count - 1)
                elif was_fetched:
                    task.success_count = max(0, task.success_count - 1)
                elif was_missing:
                    task.failed_count = max(0, task.failed_count - 1)
                
                # Add new state
                if is_edited:
                    # Treat manually resolved complete abstract as part of success_count
                    task.success_count += 1
                else:
                    task.failed_count += 1
                    
                break
                
        if not found:
            return JsonResponse({"error": f"Entry {entry_id} not found in bibliography"}, status=404)
            
    task.add_log(f"Manual update: Abstract for entry '{entry_id}' updated by user.")
    return JsonResponse({"status": "success"})

def download_bib(request, task_id):
    task = TaskManager.get_task(task_id)
    if not task:
        raise Http404("Task not found")
        
    format_type = request.GET.get('format', '').strip().lower()
    
    # If no format specified, default to original file extension
    orig_name = task.original_filename
    if not format_type:
        if orig_name.endswith('.csv'):
            format_type = 'csv'
        elif orig_name.endswith('.ris'):
            format_type = 'ris'
        else:
            format_type = 'bib'
            
    # Process base filename
    if orig_name.endswith('.bibtex'):
        name_base = orig_name[:-7]
    elif orig_name.endswith('.bib'):
        name_base = orig_name[:-4]
    elif orig_name.endswith('.csv'):
        name_base = orig_name[:-4]
    elif orig_name.endswith('.ris'):
        name_base = orig_name[:-4]
    else:
        name_base = orig_name

    if format_type == 'csv':
        import csv
        output = io.StringIO()
        with task.lock:
            entries = task.bib_database.entries
            # Collect all possible keys across all entries
            all_keys = set()
            for entry in entries:
                all_keys.update(entry.keys())
            
            # Remove ENTRYTYPE from CSV column headers to keep it clean
            all_keys.discard('ENTRYTYPE')
            
            # Standard order
            standard_fields = ['ID', 'title', 'author', 'journal', 'year', 'doi', 'abstract', 'abstract_source']
            fieldnames = [f for f in standard_fields if f in all_keys]
            extra_fields = sorted(list(all_keys - set(standard_fields)))
            fieldnames.extend(extra_fields)
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                row = {k: v for k, v in entry.items() if k in fieldnames}
                writer.writerow(row)
                
            csv_content = output.getvalue()
            
        response = HttpResponse(csv_content, content_type="text/csv")
        response['Content-Disposition'] = f'attachment; filename="resolved_{name_base}.csv"'
        return response
    elif format_type == 'ris':
        with task.lock:
            ris_content = serialize_to_ris(task.bib_database.entries)
        response = HttpResponse(ris_content, content_type="application/x-research-info-systems")
        response['Content-Disposition'] = f'attachment; filename="resolved_{name_base}.ris"'
        return response
    else:
        # Generate BibTeX content
        with task.lock:
            # Ensure every entry has ENTRYTYPE before dumping to BibTeX
            for entry in task.bib_database.entries:
                if 'ENTRYTYPE' not in entry:
                    entry['ENTRYTYPE'] = 'article'
            content = bibtexparser.dumps(task.bib_database)
            
        response = HttpResponse(content, content_type="application/x-bibtex")
        response['Content-Disposition'] = f'attachment; filename="resolved_{name_base}.bib"'
        return response
