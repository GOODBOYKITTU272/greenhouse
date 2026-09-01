with open('brain_worker.py', 'r') as f:
    text = f.read()

# Add the zip lookup function right after the imports
zip_function = '''
def lookup_zip_code(street, city, state):
    """
    Use OpenStreetMap Nominatim (free, no API key) to find a zip code
    when the candidate's profile is missing it.
    Only called once — result is saved permanently to the database.
    """
    try:
        import urllib.parse, urllib.request as ur, json as js
        query = urllib.parse.urlencode({
            'street': street or '',
            'city': city or '',
            'state': state or '',
            'country': 'US',
            'format': 'json',
            'addressdetails': '1',
            'limit': '1'
        })
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = ur.Request(url, headers={'User-Agent': 'ApplyWizz/1.0 (job application automation)'})
        with ur.urlopen(req, timeout=5) as resp:
            results = js.loads(resp.read().decode())
        if results:
            postcode = results[0].get('address', {}).get('postcode', '')
            if postcode:
                logging.info(f"  📮 Found zip code via OpenStreetMap: {postcode}")
                return postcode
    except Exception as e:
        logging.warning(f"  Could not look up zip code: {e}")
    return ''

'''

# Insert the function after the extract_resume_text function
text = text.replace(
    'def get_or_cache_candidate(supabase',
    zip_function + 'def get_or_cache_candidate(supabase'
)

# Now add the zip lookup call inside build_candidate_dict
# After zip_code is computed, if it's empty, look it up
old_zip_line = '''    return {
        # Core identity
        "applywizz_id": applywizz_id,'''

new_zip_line = '''    # If zip code is missing from the API, look it up automatically via OpenStreetMap
    if not zip_code and (city or state):
        zip_code = lookup_zip_code(street, city, state)

    return {
        # Core identity
        "applywizz_id": applywizz_id,'''

text = text.replace(old_zip_line, new_zip_line)

with open('brain_worker.py', 'w') as f:
    f.write(text)
print("Zip lookup added!")
