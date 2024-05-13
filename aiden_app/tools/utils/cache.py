import datetime
import os
import pickle
from typing import Any, Dict, List, Optional


class Cache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cache = {}
        self.load_cache()

    def load_cache(self):
        for file_name in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, file_name)
            file_mtime = os.path.getmtime(file_path)
            file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(file_mtime)
            if file_age > datetime.timedelta(days=1):
                os.remove(file_path)
            else:
                with open(file_path, "rb") as f:
                    cache_entry = pickle.load(f)
                    self.cache[cache_entry["query"]] = cache_entry

    def save_cache(self):
        for query, cache_entry in self.cache.items():
            cache_file_path = self.get_cache_file_path(*cache_entry["params"])
            with open(cache_file_path, "wb") as f:
                pickle.dump(cache_entry, f)

    def get_cache_file_path(self, *params: str) -> str:
        cache_file_name = f"_{'_'.join(params)}.pkl"
        cache_file_path = os.path.join(self.cache_dir, cache_file_name)
        return cache_file_path

    def get_cache_entry(self, query: str) -> Optional[Dict[str, Any]]:
        if query in self.cache:
            return self.cache[query]
        return None

    def add_cache_entry(self, query: str, params: List[str], results: List[Dict[str, Any]]):
        cache_entry = {
            "query": query,
            "params": params,
            "results": results,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.cache[query] = cache_entry
        self.save_cache()
