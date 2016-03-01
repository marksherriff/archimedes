import urllib.request
import re
import os.path

real_open = urllib.request.urlopen
def cachingURLOpen(url, *args, **kwargs):
    global real_open
    cacheName = ".cache-"+re.sub("[^a-zA-Z0-9]","_",url)
    if not os.path.exists(cacheName):
        with open(cacheName, 'wb') as f:
            tmp = real_open(url, *args, **kwargs)
            f.write(tmp.read())
            tmp.close()
    return open(cacheName, 'rb')
urllib.request.urlopen = cachingURLOpen


