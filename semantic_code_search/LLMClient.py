from msal import PublicClientApplication, SerializableTokenCache
import json
import os
import atexit
import requests
import time

class LLMClient:

    _ENDPOINT = 'https://fe-26.qas.bing.net/completions'
    _SCOPES = ['api://68df66a4-cad9-4bfd-872b-c6ddde00d6b2/access']
    
    def __init__(self):
        self._cache = SerializableTokenCache()
        atexit.register(lambda: 
            open('.llmapi.bin', 'w').write(self._cache.serialize())
            if self._cache.has_state_changed else None)

        self._app = PublicClientApplication('68df66a4-cad9-4bfd-872b-c6ddde00d6b2', authority='https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47', token_cache=self._cache)
        if os.path.exists('.llmapi.bin'):
            self._cache.deserialize(open('.llmapi.bin', 'r').read())

    def send_request(self, model_name, request):
        # get the token
        token = self._get_token()

        # populate the headers
        headers = {
            'Content-Type':'application/json', 
            'Authorization': 'Bearer ' + token, 
            'X-ModelType': model_name }

        body = str.encode(json.dumps(request))
        response = requests.post(LLMClient._ENDPOINT, data=body, headers=headers)
        return response.json()

    def send_stream_request(self, model_name, request):
        # get the token
        token = self._get_token()
        # populate the headers
        headers = {
            'Content-Type':'application/json', 
            'Authorization': 'Bearer ' + token, 
            'X-ModelType': model_name }

        body = str.encode(json.dumps(request))
        response = requests.post(LLMClient._ENDPOINT, data=body, headers=headers, stream=True)
        for line in response.iter_lines():
            text = line.decode('utf-8')
            if text.startswith('data: '):
                text = text[6:]
                if text == '[DONE]':
                    break
                else:
                    yield json.loads(text)       

    def _get_token(self):
        # Return access_token_cached if not expired yet
        accounts = self._app.get_accounts()
        result = None

        if accounts:
            # Assuming the end user chose this one
            chosen = accounts[0]

            # Now let's try to find a token in cache for this account
            result = self._app.acquire_token_silent(LLMClient._SCOPES, account=chosen)

        if not result:
            # So no suitable token exists in cache. Let's get a new one from AAD.
            flow = self._app.initiate_device_flow(scopes=LLMClient._SCOPES)

            if "user_code" not in flow:
                raise ValueError(
                    "Fail to create device flow. Err: %s" % json.dumps(flow, indent=4))

            print(flow['message'])

            while True:

                result = self._app.acquire_token_by_device_flow(flow)

                if "access_token" in result:
                    break

                if "error" in result and result["error"] == "authorization_pending":
                    print("Authorization pending. Waiting...")
                    time.sleep(flow["interval"])

                elif "error" in result:
                    raise ValueError(
                        "Failed to acquire token. Err: %s" % json.dumps(result, indent=4))

                else:
                    raise ValueError(
                        "Unexpected error. Err: %s" % json.dumps(result, indent=4))

            # cache the token
            self._cache.add(result)
            with open('.llmapi.bin', 'w') as f:
                f.write(self._cache.serialize())

        return result["access_token"]

