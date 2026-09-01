with open('applywizz_brain.py', 'r') as f:
    text = f.read()

old_parser = """    def extract_job_info(self, url):
        if 'grnh.se' in url:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    url = response.url
                    print(f"Resolved shortlink to: {url}")
            except Exception as e:
                print(f"Failed to resolve shortlink: {e}")

        parsed = urlparse(url)
        parts = parsed.path.strip('/').split('/')
        if len(parts) >= 3 and parts[-2] == 'jobs':
            return parts[-3], parts[-1]
        if len(parts) >= 3 and parts[1] == 'jobs':
            return parts[0], parts[2]
        return None, None"""

new_parser = """    def extract_job_info(self, url):
        from urllib.parse import parse_qs

        # Resolve grnh.se shortlinks AND app.greenhouse.io embed links
        if 'grnh.se' in url or 'app.greenhouse.io' in url or 'embed/job_app' in url:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    url = response.url
                    print(f"Resolved shortlink to: {url}")
            except Exception as e:
                print(f"Failed to resolve shortlink: {e}")

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        # Handle embed format: job-boards.greenhouse.io/embed/job_app?for=company&token=jobid
        if 'embed/job_app' in url:
            board_token = qs.get('for', [None])[0]
            job_id = qs.get('token', [None])[0]
            if board_token and job_id:
                print(f"Parsed embed URL: board={board_token}, job={job_id}")
                return board_token, job_id

        # Standard format: job-boards.greenhouse.io/{board_token}/jobs/{job_id}
        parts = parsed.path.strip('/').split('/')
        if len(parts) >= 3 and parts[-2] == 'jobs':
            return parts[-3], parts[-1]
        if len(parts) >= 3 and parts[1] == 'jobs':
            return parts[0], parts[2]
        return None, None"""

text = text.replace(old_parser, new_parser)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Embed URL parser added!")
