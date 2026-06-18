import itertools
import sys
import os
import time
import random
import re
import pyfiglet
import threading
import queue
import json
from datetime import datetime

# Import colorama untuk warna
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)  # Auto reset warna setelah print
    COLORAMA_AVAILABLE = True
    # Ensure RESET_ALL exists (some colorama versions might not have it)
    try:
        _ = Style.RESET_ALL  # Test if it exists
    except AttributeError:
        # If RESET_ALL doesn't exist, create it
        try:
            Style.RESET_ALL = Style.RESET if hasattr(Style, 'RESET') else ""
        except:
            Style.RESET_ALL = ""
except (ImportError, AttributeError, Exception) as e:
    COLORAMA_AVAILABLE = False
    # Dummy colors jika colorama tidak tersedia
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

# Safe print function yang tidak akan crash meskipun colorama error
def safe_print(*args, **kwargs):
    """Print function yang aman dari error colorama"""
    try:
        print(*args, **kwargs)
    except (AttributeError, Exception) as e:
        # Fallback: print tanpa formatting jika colorama error
        try:
            # Remove colorama codes dari string jika ada
            import re
            clean_args = []
            for arg in args:
                try:
                    arg_str = str(arg)
                    # Remove ANSI escape codes
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    clean_arg = ansi_escape.sub('', arg_str)
                    clean_args.append(clean_arg)
                except:
                    clean_args.append(str(arg))
            print(*clean_args, **kwargs)
        except Exception as e2:
            # Ultimate fallback: print as-is atau minimal
            try:
                print(*[str(a) for a in args], **kwargs)
            except:
                # Last resort: print error message
                print(f"[Print Error: {type(e).__name__}]")

# Import shodan untuk facet dan download
try:
    import shodan
    SHODAN_AVAILABLE = True
except ImportError:
    SHODAN_AVAILABLE = False
    print(f"{Fore.YELLOW}[!] Warning: shodan library not installed. Install with: pip install shodan{Fore.RESET}")

# Import Redis untuk deduplication
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print(f"{Fore.YELLOW}[!] Warning: redis library not installed. Install with: pip install redis{Fore.RESET}")

# HARDCODED API KEY - GANTI DENGAN API KEY ANDA
SHODAN_API_KEY = "PVgkALcMHk4j1ypxfutvsyPwOcANV6Vn"

# Redis Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # Set jika Redis menggunakan password
REDIS_KEY_PREFIX = "shodan:results:"  # Prefix untuk key di Redis

# HIGH QUALITY DATASET - Curated untuk menghasilkan kombinasi yang lebih relevan dan mengurangi kombinasi yang tidak berguna
# Dataset ini sudah dioptimasi: hanya item yang paling umum dan relevan, mengurangi noise
DATA_POOLS = {
    "PRODUCTS": [
        # Web Servers (Top 5 Most Common)
        'nginx', 'Apache', 'Microsoft-IIS', 'LiteSpeed', 'Apache Tomcat',
        # Application Servers (Top 3)
        'Node.js', 'Gunicorn', 'uWSGI',
        # Databases (Top 7 Most Popular)
        'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
        'Microsoft SQL Server', 'Oracle Database',
        # DevOps & Containers (Top 4)
        'Docker', 'Kubernetes', 'Jenkins', 'GitLab',
        # Monitoring & Analytics (Top 4)
        'Grafana', 'Kibana', 'Prometheus', 'Zabbix',
        # VPN & Remote Access (Top 4)
        'OpenSSH', 'RDP', 'VNC', 'OpenVPN',
        # Security & Firewall (Top 4)
        'FortiGate', 'Palo Alto', 'Cisco', 'pfSense',
        # Network Equipment (Top 4)
        'MikroTik', 'Ubiquiti', 'Synology', 'QNAP',
        # CMS & Web Apps (Top 4)
        'WordPress', 'Joomla', 'Drupal', 'Magento',
        # Control Panels (Top 3)
        'cPanel', 'Plesk', 'Webmin',
        # Media Servers (Top 2)
        'Plex Media Server', 'Jellyfin'
    ],
    "PORTS": [
        # HTTP/HTTPS (Most Common - 6 ports)
        '80', '443', '8080', '8443', '8000', '8888',
        # Databases (Top 6)
        '3306', '5432', '27017', '6379', '9200', '1433',
        # SSH & Remote (Top 4)
        '22', '3389', '5900', '5901',
        # Email (Top 4)
        '25', '587', '993', '995',
        # Docker & Kubernetes (Top 4)
        '2375', '2376', '10250', '6443',
        # Monitoring (Top 3)
        '9090', '3000', '5601',
        # Message Queue (Top 2)
        '5672', '1883',
        # SMB (Top 2)
        '445', '139',
        # VPN (Top 3)
        '1194', '500', '4500'
    ],
    "ORGS": [
        # Cloud Providers (Top Tier - 5)
        'Amazon', 'Google', 'Microsoft', 'DigitalOcean', 'Oracle',
        # Major Hosting (Top 4)
        'OVH', 'Hetzner', 'Linode', 'Vultr',
        # CDN & Security (Top 2)
        'Cloudflare', 'Akamai',
        # Major ISPs (Top 3)
        'Comcast', 'Verizon', 'AT&T',
        # International Telecom (Top 4)
        'China Telecom', 'NTT', 'Deutsche Telekom', 'Vodafone',
        # Organizations (Top 3)
        'University', 'Government', 'Bank'
    ],
    "COUNTRIES": [
        # Top 20 Most Common Countries (reduced from 50+)
        'US', 'CN', 'DE', 'GB', 'FR', 'JP', 'IN', 'BR', 'RU', 'CA',
        'AU', 'NL', 'IT', 'ES', 'KR', 'SE', 'PL', 'MX', 'ID', 'SG'
    ],
    "TITLES": [
        # Admin & Login Pages (Top 6)
        'Login', 'Admin', 'Administrator', 'Sign In', 'Dashboard', 'Control Panel',
        # Default Pages (Top 3)
        'Index of', 'Welcome', 'Default Page',
        # Service Dashboards (Top 7)
        'Grafana', 'Kibana', 'Jenkins', 'GitLab', 'phpMyAdmin',
        'Kubernetes Dashboard', 'RouterOS',
        # Error Pages (Top 2)
        '403 Forbidden', '404 Not Found',
        # System Pages (Top 3)
        'VMware ESXi', 'Proxmox VE', 'Synology DiskStation',
        # Security Indicators (Top 2)
        'Hacked', 'Hacked By'
    ],
    "VULNS": [
        # Recent Critical CVEs (2023-2024 - Top 5)
        'CVE-2024-1709', 'CVE-2024-21893', 'CVE-2023-46805', 'CVE-2023-22515',
        'CVE-2023-20198',
        # Major Historical CVEs (Top 7)
        'CVE-2021-44228', 'CVE-2021-26855', 'CVE-2021-41773',
        'CVE-2020-0796', 'CVE-2019-11510', 'CVE-2019-19781',
        'CVE-2017-0144', 'CVE-2014-0160'
    ],
    "OS": [
        # Windows (Top 4)
        'Windows', 'Windows Server 2022', 'Windows Server 2019', 'Windows 10',
        # Linux (Most Common - Top 4)
        'Linux', 'Ubuntu', 'Debian', 'CentOS',
        # Network OS (Top 2)
        'MikroTik RouterOS', 'Cisco IOS',
        # Other (Top 2)
        'FreeBSD', 'Synology DSM'
    ],
    "COMPONENTS": [
        # Frontend Frameworks (Top 5)
        'jQuery', 'Bootstrap', 'React', 'Vue.js', 'Angular',
        # Backend (Top 3)
        'Express', 'PHP', 'Python',
        # Analytics (Top 2)
        'Google Analytics', 'Google Tag Manager',
        # Security (Top 2)
        'Cloudflare', 'Wordfence',
        # Libraries (Top 1)
        'OpenSSL'
    ],
    "CERT_ISSUERS": [
        # Most Common Certificate Authorities (Top 7)
        "Let's Encrypt", "DigiCert", "Sectigo", "Cloudflare",
        "Amazon", "Google Trust Services", "GoDaddy"
    ],
    "BANNERS": [
        # Authentication (Top 2)
        'Basic realm=', 'WWW-Authenticate',
        # Server Headers (Top 3)
        'server: nginx', 'server: apache', 'server: microsoft-iis',
        # Default Messages (Top 3)
        'Welcome to nginx', 'It works!', 'Index of /',
        # Security Indicators (Top 2)
        'hacked', 'hacked by'
    ]
}

SHODAN_PREFIXES = {
    "PRODUCTS": "product",
    "PORTS": "port",
    "ORGS": "org",
    "COUNTRIES": "country",
    "TITLES": "http.title",
    "VULNS": "vuln",
    "OS": "os",
    "COMPONENTS": "http.component",
    "CERT_ISSUERS": "ssl.cert.issuer.cn",
    "BANNERS": ""
}

# Mapping untuk facet fields di Shodan API
SHODAN_FACET_FIELDS = {
    "PRODUCTS": "product",
    "PORTS": "port",
    "ORGS": "org",
    "COUNTRIES": "country",
    "TITLES": "http.title",
    "VULNS": "vuln",
    "OS": "os",
    "COMPONENTS": "http.component",
    "CERT_ISSUERS": "ssl.cert.issuer.cn",
    "BANNERS": ""  # BANNERS tidak bisa di-facet, tetap menggunakan hardcoded
}

# Cache file untuk menyimpan top items
DATASET_CACHE_FILE = "shodan_top_datasets_cache.json"

def fetch_top_items_from_shodan(api_key, category, top_n=100, rate_limiter_instance=None):
    """Fetch top N items from Shodan for a specific category using facets API"""
    if not SHODAN_AVAILABLE:
        return []
    
    facet_field = SHODAN_FACET_FIELDS.get(category)
    if not facet_field:
        # Kategori yang tidak bisa di-facet (seperti BANNERS)
        return []
    
    if rate_limiter_instance:
        rate_limiter_instance.acquire()
    
    try:
        api = shodan.Shodan(api_key)
        
        # Test API key first dengan info endpoint
        try:
            api_info = api.info()
            # Check if API key has search credits
            if 'plan' in api_info:
                plan = api_info.get('plan', '')
                if plan == 'free':
                    # Free plan might have limited facets access
                    pass
        except Exception as info_e:
            if rate_limiter_instance:
                rate_limiter_instance.release()
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}API Key validation failed:{Fore.RESET} {Fore.WHITE}{info_e}{Fore.RESET}")
            return []
        
        # Query untuk mendapatkan semua data
        # Gunakan query kosong untuk mendapatkan semua data
        query = ""
        
        # Fetch facets dengan limit top_n (Shodan API biasanya mendukung hingga 100)
        facet_limit = min(top_n, 100)  # Shodan biasanya limit 100 per facet
        
        # Format facets yang benar untuk Shodan API
        # Format: [{"field_name": limit}]
        facets_param = [{facet_field: facet_limit}]
        
        # Try using count API first (lebih efisien untuk facets)
        result = None
        last_error = None
        
        # Try multiple approaches
        approaches = [
            ("count with empty query", lambda: api.count("", facets=facets_param)),
            ("count with * query", lambda: api.count("*", facets=facets_param)),
            ("search with * query", lambda: api.search("*", facets=facets_param, page=1)),
        ]
        
        for approach_name, approach_func in approaches:
            try:
                result = approach_func()
                break  # Success, exit loop
            except shodan.exception.APIError as e:
                last_error = e
                # If it's a rate limit, don't try other approaches
                if 'rate limit' in str(e).lower() or '429' in str(e):
                    raise
                continue  # Try next approach
            except Exception as e:
                last_error = e
                continue  # Try next approach
        
        # If all approaches failed, raise the last error
        if result is None:
            if last_error:
                raise last_error
            else:
                raise Exception("All API approaches failed without error")
        
        top_items = []
        if result and isinstance(result, dict) and 'facets' in result:
            facets_dict = result['facets']
            if isinstance(facets_dict, dict) and facet_field in facets_dict:
                facet_data = facets_dict[facet_field]
                if isinstance(facet_data, list):
                    for item in facet_data:
                        # Handle different response formats
                        if isinstance(item, dict):
                            value = item.get('value') or item.get('id')
                            count = item.get('count', 0)
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            # Format: [value, count]
                            value = item[0]
                            count = item[1] if len(item) > 1 else 0
                        else:
                            continue
                        
                        # Hanya ambil items dengan count > 0 dan value tidak kosong
                        if count > 0 and value is not None:
                            # Convert ke string dan clean
                            clean_val = str(value).strip()
                            if clean_val and clean_val.lower() not in ['null', 'none', '']:
                                top_items.append(clean_val)
        
        # Return top N items
        return top_items[:top_n]
        
    except shodan.exception.APIError as e:
        error_msg = str(e).lower()
        error_code = getattr(e, 'code', None)
        
        if 'rate limit' in error_msg or '429' in str(e) or error_code == 429:
            if rate_limiter_instance:
                rate_limiter_instance.release()
            print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Rate limit hit while fetching {category}. Waiting 60s...{Fore.RESET}")
            time.sleep(60)
            # Retry once after waiting
            if rate_limiter_instance:
                rate_limiter_instance.acquire()
            try:
                api = shodan.Shodan(api_key)
                facet_limit = min(top_n, 100)
                facets_param = [{facet_field: facet_limit}]
                try:
                    result = api.count("*", facets=facets_param)
                except:
                    result = api.search("*", facets=facets_param, page=1)
                
                top_items = []
                if result and 'facets' in result:
                    facet_data = result['facets'].get(facet_field, [])
                    for item in facet_data:
                        if isinstance(item, dict):
                            value = item.get('value') or item.get('id')
                            count = item.get('count', 0)
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            value = item[0]
                            count = item[1] if len(item) > 1 else 0
                        else:
                            continue
                        if count > 0 and value is not None:
                            clean_val = str(value).strip()
                            if clean_val and clean_val.lower() != 'null':
                                top_items.append(clean_val)
                return top_items[:top_n]
            except Exception as retry_e:
                print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Retry failed for {category}:{Fore.RESET} {Fore.WHITE}{retry_e}{Fore.RESET}")
                return []
        else:
            # Print detailed error information
            error_details = f"Code: {error_code}, Message: {str(e)}" if error_code else str(e)
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}API Error fetching {category}:{Fore.RESET} {Fore.WHITE}{error_details}{Fore.RESET}")
        return []
    except Exception as e:
        # Print more detailed error information
        error_type = type(e).__name__
        error_msg = str(e)
        error_repr = repr(e)
        
        # Check if it's a specific Shodan error
        if hasattr(e, 'code'):
            error_code = e.code
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Error fetching {category} (Code: {error_code}, Type: {error_type}):{Fore.RESET} {Fore.WHITE}{error_msg}{Fore.RESET}")
        else:
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Unexpected error fetching {category} (Type: {error_type}):{Fore.RESET} {Fore.WHITE}{error_msg}{Fore.RESET}")
            # If error message is just "0", it might be a specific issue
            if error_msg == "0" or error_repr == "0":
                print(f"{Fore.YELLOW}   {Style.BRIGHT}Note:{Style.RESET_ALL} {Fore.WHITE}This might indicate an API access issue or invalid facet field.{Fore.RESET}")
        
        return []
    finally:
        if rate_limiter_instance:
            rate_limiter_instance.release()

def update_datasets_from_shodan(api_key, top_n=100, force_refresh=False, rate_limiter_instance=None):
    """Update DATA_POOLS dengan top items dari Shodan API"""
    global DATA_POOLS
    
    # Load cache jika ada dan tidak force refresh
    if not force_refresh and os.path.exists(DATASET_CACHE_FILE):
        try:
            with open(DATASET_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                # Check jika cache masih valid (kurang dari 7 hari)
                if 'timestamp' in cached_data:
                    cache_time = datetime.fromisoformat(cached_data['timestamp'])
                    age_days = (datetime.now() - cache_time).days
                    if age_days < 7:
                        print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Loading datasets from cache{Fore.RESET} {Fore.WHITE}({age_days} days old){Fore.RESET}")
                        cached_datasets = cached_data.get('datasets', {})
                        # Merge dengan default untuk memastikan semua kategori ada
                        for key in DATA_POOLS.keys():
                            if key in cached_datasets:
                                DATA_POOLS[key] = cached_datasets[key]
                        return True
        except Exception as e:
            print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Error loading cache:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
    
    if not SHODAN_AVAILABLE:
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Shodan library not available. Using default datasets.{Fore.RESET}")
        return False
    
    if api_key == "YOUR_API_KEY_HERE":
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Shodan API Key not set. Using default datasets.{Fore.RESET}")
        return False
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}[ FETCHING TOP ITEMS FROM SHODAN ]{Style.RESET_ALL}")
    print(f"{Fore.BLUE}Fetching top {top_n} items for each category...{Fore.RESET}\n")
    
    # Backup default pools untuk fallback
    default_pools = DATA_POOLS.copy()
    updated_pools = {}
    categories = list(DATA_POOLS.keys())
    
    for idx, category in enumerate(categories, 1):
        print(f"{Fore.CYAN}[{idx}/{len(categories)}]{Fore.RESET} {Fore.YELLOW}Fetching {category}...{Fore.RESET}", end=" ")
        
        # Check if category can be faceted
        facet_field = SHODAN_FACET_FIELDS.get(category)
        if not facet_field:
            # Kategori yang tidak bisa di-facet (seperti BANNERS), gunakan default
            updated_pools[category] = default_pools[category]
            print(f"{Fore.BLUE}⊘{Fore.RESET} {Fore.BLUE}Using default ({len(default_pools[category])} items - not facetable){Fore.RESET}")
            continue
        
        top_items = fetch_top_items_from_shodan(api_key, category, top_n, rate_limiter_instance)
        
        if top_items and len(top_items) > 0:
            updated_pools[category] = top_items
            print(f"{Fore.GREEN}✓{Fore.RESET} {Fore.GREEN}{len(top_items)}{Fore.RESET} {Fore.WHITE}items{Fore.RESET}")
        else:
            # Fallback ke default jika fetch gagal
            updated_pools[category] = default_pools[category]
            print(f"{Fore.YELLOW}⚠{Fore.RESET} {Fore.YELLOW}Using default ({len(default_pools[category])} items){Fore.RESET}")
        
        # Small delay between categories
        if rate_limiter_instance:
            time.sleep(0.5)
    
    # Update global DATA_POOLS
    DATA_POOLS = updated_pools
    
    # Save to cache
    try:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'datasets': DATA_POOLS
        }
        with open(DATASET_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Datasets cached to{Fore.RESET} {Fore.YELLOW}{DATASET_CACHE_FILE}{Fore.RESET}")
    except Exception as e:
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Error saving cache:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
    
    return True

def clean_value(val):
    val = str(val).strip()
    if any(char in val for char in [' ', '=', '/', ':', '-']):
        if not (val.startswith('"') and val.endswith('"')):
            return f'"{val}"'
    return val

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    text = re.sub(r'_+', '_', text)
    text = text.strip('_ ')
    return text[:50]

# ========== SHODAN FACET & DOWNLOAD FUNCTIONS ==========
shodan_lock = threading.Lock()
shodan_written_ips = set()

# Redis connection pool (thread-safe)
redis_client = None
redis_lock = threading.Lock()

def init_redis():
    """Initialize Redis connection"""
    global redis_client
    if not REDIS_AVAILABLE:
        return None
    
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # Test connection
        redis_client.ping()
        print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Redis connected:{Fore.RESET} {Fore.YELLOW}{REDIS_HOST}:{REDIS_PORT}{Fore.RESET}")
        return redis_client
    except redis.ConnectionError as e:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Redis connection error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.WHITE}Continuing without Redis deduplication...{Fore.RESET}")
        return None
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Redis initialization error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.WHITE}Continuing without Redis deduplication...{Fore.RESET}")
        return None

def check_redis_exists(entry):
    """Check if entry exists in Redis"""
    global redis_client
    if not redis_client:
        return False
    
    try:
        key = f"{REDIS_KEY_PREFIX}{entry}"
        exists = redis_client.exists(key)
        return exists == 1
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Redis check error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
        return False

def save_to_redis(entry):
    """Save entry to Redis for deduplication"""
    global redis_client
    if not redis_client:
        return False
    
    try:
        key = f"{REDIS_KEY_PREFIX}{entry}"
        # Set dengan expiration 30 hari (optional, bisa diubah)
        redis_client.setex(key, 30 * 24 * 60 * 60, "1")
        return True
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Redis save error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
        return False

# Rate Limiting Configuration
class RateLimiter:
    """Rate limiter untuk menghindari rate limiting dari Shodan API"""
    def __init__(self, max_requests_per_minute=60, max_concurrent=3):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent = max_concurrent
        self.request_times = []
        self.semaphore = threading.Semaphore(max_concurrent)
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_delay = 60.0 / max_requests_per_minute  # Minimum delay between requests
    
    def acquire(self):
        """Acquire permission to make a request"""
        self.semaphore.acquire()
        with self.lock:
            current_time = time.time()
            # Remove requests older than 1 minute
            self.request_times = [t for t in self.request_times if current_time - t < 60]
            
            # Check if we're at the rate limit
            if len(self.request_times) >= self.max_requests_per_minute:
                # Wait until we can make another request
                oldest_request = min(self.request_times)
                wait_time = 60 - (current_time - oldest_request) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
                    # Clean up again after waiting
                    current_time = time.time()
                    self.request_times = [t for t in self.request_times if current_time - t < 60]
            
            # Ensure minimum delay between requests
            if self.last_request_time > 0:
                elapsed = current_time - self.last_request_time
                if elapsed < self.min_delay:
                    time.sleep(self.min_delay - elapsed)
            
            self.request_times.append(time.time())
            self.last_request_time = time.time()
    
    def release(self):
        """Release the semaphore after request is done"""
        self.semaphore.release()

# Global rate limiter instance
rate_limiter = None

def is_recent(timestamp, after_date):
    try:
        ts = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        return ts >= after_date
    except Exception:
        return False

def check_facet(api_key, query, rate_limiter_instance=None):
    """Check facet count for a query with rate limiting"""
    if rate_limiter_instance:
        rate_limiter_instance.acquire()
    
    try:
        api = shodan.Shodan(api_key)
        result = api.count(query)
        total = result.get('total', 0)
        return total
    except shodan.exception.APIError as e:
        error_msg = str(e).lower()
        if 'rate limit' in error_msg or '429' in str(e):
            try:
                safe_print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Rate limit hit for facet check. Waiting 60s...{Fore.RESET}")
            except:
                print(f"[!] Rate limit hit for facet check. Waiting 60s...")
            try:
                time.sleep(60)
            except:
                pass
        else:
            try:
                safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Facet check error for{Fore.RESET} {Fore.CYAN}'{query}':{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
            except:
                print(f"[!] Facet check error for '{query}': {e}")
        return 0
    except Exception as e:
        try:
            safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Unexpected error in facet check:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
        except:
            print(f"[!] Unexpected error in facet check: {e}")
        return 0
    finally:
        if rate_limiter_instance:
            try:
                rate_limiter_instance.release()
            except:
                pass

def fetch_and_save(api_key, query, limit, after_date, output_file, rate_limiter_instance=None, redis_client_instance=None):
    """Download results from Shodan and save to file with rate limiting and Redis deduplication"""
    api = shodan.Shodan(api_key)
    results_found = 0
    seen = set()  # Local seen set untuk thread ini
    retry_count = 0
    max_retries = 3

    try:
        safe_print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Downloading:{Fore.RESET} {Fore.YELLOW}{query}{Fore.RESET}")
    except:
        print(f"[+] Downloading: {query}")

    while retry_count < max_retries:
        try:
            # Acquire rate limiter before starting download
            if rate_limiter_instance:
                rate_limiter_instance.acquire()
            
            cursor_count = 0
            for count, result in enumerate(api.search_cursor(query), start=1):
                cursor_count = count
                timestamp = result.get("timestamp")
                ip = result.get("ip_str")
                hostnames = result.get("hostnames", [])

                if timestamp and is_recent(timestamp, after_date):
                    entries = []

                    if ip and ":" not in ip and not ip.startswith("2600:"):
                        entries.append(ip)

                    if hostnames:
                        entries.extend(hostnames)

                    for entry in entries:
                        entry = entry.strip().lower()
                        if not entry or entry in seen:
                            continue
                        
                        seen.add(entry)
                        
                        # Check Redis untuk deduplication (realtime)
                        is_duplicate = False
                        if redis_client_instance:
                            is_duplicate = check_redis_exists(entry)
                        
                        # Check local set juga (untuk thread safety)
                        with shodan_lock:
                            if entry in shodan_written_ips:
                                is_duplicate = True
                        
                        # Jika bukan duplicate, simpan ke file dan Redis (realtime)
                        if not is_duplicate:
                            with shodan_lock:
                                # Double check dengan lock
                                if entry not in shodan_written_ips:
                                    # Simpan ke file secara realtime
                                    with open(output_file, "a", encoding="utf-8") as f:
                                        f.write(entry + "\n")
                                    
                                    # Simpan ke Redis untuk deduplication (realtime)
                                    if redis_client_instance:
                                        save_to_redis(entry)
                                    
                                    # Update local set
                                    shodan_written_ips.add(entry)
                                    results_found += 1
                                    
                                    if results_found % 10 == 0:
                                        try:
                                            safe_print(f"{Fore.CYAN}[{Fore.YELLOW}{query}{Fore.CYAN}]{Fore.RESET} {Fore.GREEN}→{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{results_found}{Style.RESET_ALL} {Fore.WHITE}results saved...{Fore.RESET}")
                                        except:
                                            print(f"[{query}] → {results_found} results saved...")

                if results_found >= limit:
                    break

                # Rate limiting: small delay every 10 results
                if count % 10 == 0:
                    time.sleep(0.1)

            # Release rate limiter after download
            if rate_limiter_instance:
                rate_limiter_instance.release()
            
            # Success - break retry loop
            break

        except shodan.exception.APIError as e:
            error_msg = str(e).lower()
            
            # Release rate limiter on error
            if rate_limiter_instance:
                rate_limiter_instance.release()
            
            if 'rate limit' in error_msg or '429' in str(e) or 'throttle' in error_msg:
                retry_count += 1
                wait_time = min(60 * retry_count, 300)  # Exponential backoff, max 5 minutes
                try:
                    safe_print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Rate limit detected for{Fore.RESET} {Fore.CYAN}'{query}'.{Fore.RESET} {Fore.WHITE}Waiting {Fore.YELLOW}{wait_time}s{Fore.WHITE} (retry {Fore.CYAN}{retry_count}/{max_retries}{Fore.WHITE})...{Fore.RESET}")
                except:
                    print(f"[!] Rate limit detected for '{query}'. Waiting {wait_time}s (retry {retry_count}/{max_retries})...")
                try:
                    time.sleep(wait_time)
                except:
                    pass
                
                if retry_count >= max_retries:
                    try:
                        safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Max retries reached for{Fore.RESET} {Fore.CYAN}'{query}'.{Fore.RESET} {Fore.WHITE}Skipping.{Fore.RESET}")
                    except:
                        print(f"[!] Max retries reached for '{query}'. Skipping.")
                    return
            else:
                try:
                    safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Error in query{Fore.RESET} {Fore.CYAN}'{query}':{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
                except:
                    print(f"[!] Error in query '{query}': {e}")
                return
        except Exception as e:
            if rate_limiter_instance:
                try:
                    rate_limiter_instance.release()
                except:
                    pass
            try:
                safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Unexpected error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
            except:
                print(f"[!] Unexpected error: {e}")
            return

    if results_found == 0:
        try:
            safe_print(f"{Fore.YELLOW}{Style.BRIGHT}[-]{Style.RESET_ALL} {Fore.WHITE}0 Results for:{Fore.RESET} {Fore.CYAN}{query}{Fore.RESET}")
        except:
            print(f"[-] 0 Results for: {query}")
    else:
        try:
            safe_print(f"{Fore.GREEN}{Style.BRIGHT}[✓]{Style.RESET_ALL} {Fore.CYAN}Done:{Fore.RESET} {Fore.YELLOW}{query}{Fore.RESET} {Fore.GREEN}→{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{results_found}{Style.RESET_ALL} {Fore.WHITE}results{Fore.RESET}")
        except:
            print(f"[✓] Done: {query} → {results_found} results")

def process_query_facet(api_key, query, after_date, limit, output_file, facet_threshold=0, rate_limiter_instance=None, redis_client_instance=None):
    """Process a single query: check facet, then download if threshold met"""
    try:
        safe_print(f"\n{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.CYAN}Checking facet for:{Fore.RESET} {Fore.YELLOW}{query}{Fore.RESET}")
    except:
        print(f"\n[?] Checking facet for: {query}")
    
    try:
        facet_count = check_facet(api_key, query, rate_limiter_instance)
    except Exception as e:
        try:
            safe_print(f"{Fore.RED}[!] Error checking facet: {e}{Fore.RESET}")
        except:
            print(f"[!] Error checking facet: {e}")
        return  # Skip this query if facet check fails
    
    try:
        safe_print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL} {Fore.CYAN}Facet count:{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{facet_count:,}{Style.RESET_ALL}")
    except:
        print(f"[i] Facet count: {facet_count:,}")
    
    if facet_count > 0:
        try:
            safe_print(f"{Fore.GREEN}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.CYAN}Facet ={Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{facet_count:,}{Fore.RESET_ALL} {Fore.WHITE}(> 0),{Fore.RESET} {Fore.GREEN}starting automatic download...{Fore.RESET}")
        except:
            print(f"[!] Facet = {facet_count:,} (> 0), starting automatic download...")
        
        # Download tetap berjalan meskipun ada error print
        try:
            fetch_and_save(api_key, query, limit, after_date, output_file, rate_limiter_instance, redis_client_instance)
        except Exception as e:
            try:
                safe_print(f"{Fore.RED}[!] Download error for {query}: {e}{Fore.RESET}")
            except:
                print(f"[!] Download error for {query}: {e}")
    else:
        try:
            safe_print(f"{Fore.YELLOW}{Style.BRIGHT}[-]{Style.RESET_ALL} {Fore.WHITE}No results found for query{Fore.RESET}")
        except:
            print(f"[-] No results found for query")
    
    # Small delay between queries to avoid hammering the API
    try:
        time.sleep(0.3)
    except:
        pass

def shodan_worker(api_key, after_date, limit, output_file, task_queue, facet_threshold, rate_limiter_instance, redis_client_instance):
    """Worker thread function for Shodan processing with rate limiting and Redis"""
    max_retries = 3
    retry_count = 0
    
    while True:
        try:
            # Check if queue is empty
            if task_queue.empty():
                break
            
            query = task_queue.get_nowait()
            
            # Process query - tetap lanjut meskipun ada error
            try:
                process_query_facet(api_key, query, after_date, limit, output_file, facet_threshold, rate_limiter_instance, redis_client_instance)
            except Exception as process_error:
                # Error dalam process_query_facet tidak menghentikan worker
                try:
                    safe_print(f"{Fore.YELLOW}[!] Error processing query '{query}': {process_error}{Fore.RESET}")
                except:
                    print(f"[!] Error processing query '{query}': {process_error}")
                # Continue to next query
            
            task_queue.task_done()
            retry_count = 0  # Reset retry count on success
            
        except queue.Empty:
            break
        except Exception as e:
            retry_count += 1
            try:
                safe_print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.RED}Worker error:{Fore.RESET} {Fore.WHITE}{e}{Fore.RESET}")
            except:
                print(f"[!] Worker error: {e}")
            
            # Jika terlalu banyak retry, break untuk menghindari infinite loop
            if retry_count >= max_retries:
                try:
                    safe_print(f"{Fore.RED}[!] Max retries reached. Worker stopping.{Fore.RESET}")
                except:
                    print(f"[!] Max retries reached. Worker stopping.")
                break
            
            try:
                time.sleep(5)
            except:
                pass

def run_facet_and_download(query_file, api_key, after_date_str="2024-01-01", limit=10000000, num_threads=4, facet_threshold=0,
                          max_requests_per_minute=60, max_concurrent=3):
    """Run facet check and auto-download for queries in file with rate limiting and Redis deduplication"""
    global rate_limiter, redis_client
    
    if not SHODAN_AVAILABLE:
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Shodan library not available. Skipping facet/download.{Fore.RESET}")
        return
    
    if api_key == "YOUR_API_KEY_HERE":
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.RED}ERROR:{Fore.RESET} {Fore.WHITE}Please set SHODAN_API_KEY in the script!{Fore.RESET}")
        return
    
    try:
        after_date = datetime.strptime(after_date_str, "%Y-%m-%d")
    except ValueError:
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Invalid date format. Using default: 2024-01-01{Fore.RESET}")
        after_date = datetime.strptime("2024-01-01", "%Y-%m-%d")
    
    base_name = os.path.splitext(os.path.basename(query_file))[0]
    output_file = f"{base_name}_results.txt"
    
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except OSError:
            pass
    
    try:
        with open(query_file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}File{Fore.RESET} {Fore.CYAN}'{query_file}'{Fore.RESET} {Fore.YELLOW}not found.{Fore.RESET}")
        return
    
    # Initialize rate limiter
    rate_limiter = RateLimiter(max_requests_per_minute=max_requests_per_minute, max_concurrent=max_concurrent)
    
    # Initialize Redis for deduplication
    redis_client = init_redis()
    redis_status = "Enabled" if redis_client else "Disabled (not available)"
    redis_color = Fore.GREEN if redis_client else Fore.YELLOW
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}{Style.BRIGHT}Starting Shodan Facet Check & Auto-Download:{Style.RESET_ALL}")
    print(f"    {Fore.BLUE}Queries:{Fore.RESET} {Fore.YELLOW}{len(queries):,}{Fore.RESET}")
    print(f"    {Fore.BLUE}Threads:{Fore.RESET} {Fore.YELLOW}{num_threads}{Fore.RESET}")
    print(f"    {Fore.BLUE}Facet threshold:{Fore.RESET} {Fore.YELLOW}{facet_threshold:,}{Fore.RESET}")
    print(f"    {Fore.BLUE}Rate Limit:{Fore.RESET} {Fore.YELLOW}{max_requests_per_minute}{Fore.RESET} {Fore.WHITE}requests/minute{Fore.RESET}")
    print(f"    {Fore.BLUE}Max Concurrent:{Fore.RESET} {Fore.YELLOW}{max_concurrent}{Fore.RESET}")
    print(f"    {Fore.BLUE}Redis Deduplication:{Fore.RESET} {redis_color}{redis_status}{Fore.RESET}")
    print(f"    {Fore.BLUE}Output:{Fore.RESET} {Fore.CYAN}{output_file}{Fore.RESET}\n")
    
    q = queue.Queue()
    for query in queries:
        q.put(query)
    
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=shodan_worker, args=(api_key, after_date, limit, output_file, q, facet_threshold, rate_limiter, redis_client))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    # Get Redis stats if available
    redis_stats = ""
    if redis_client:
        try:
            redis_count = len(redis_client.keys(f"{REDIS_KEY_PREFIX}*"))
            redis_stats = f" (Redis: {redis_count} unique entries)"
        except:
            pass
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}✅{Style.RESET_ALL} {Fore.CYAN}Shodan processing finished.{Fore.RESET} {Fore.WHITE}Total unique IPs:{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{len(shodan_written_ips):,}{Style.RESET_ALL} {Fore.WHITE}in{Fore.RESET} {Fore.CYAN}{output_file}{Fore.RESET}{Fore.BLUE}{redis_stats}{Fore.RESET}")
# ========== END SHODAN FUNCTIONS ==========

def generate_queries(selected_keys, limit=0, manual_keywords_list=None):
    lists_to_combine = [DATA_POOLS[k] for k in selected_keys]
    
    # 1. GENERATE QUERIES WITH MANUAL KEYWORDS (IF ANY)
    if manual_keywords_list:
        for keyword in manual_keywords_list:
            
            # Cartesian Mode for Manual
            if limit == 0:
                for combination in itertools.product(*lists_to_combine):
                    parts = [keyword]
                    for i, raw_val in enumerate(combination):
                        key_name = selected_keys[i]
                        prefix = SHODAN_PREFIXES.get(key_name, "")
                        val = clean_value(raw_val)
                        if prefix:
                            part = f'{prefix}:{val}'
                        else:
                            part = f'{val}'
                        parts.append(part)
                    yield " ".join(parts)
            
            # Random Mode for Manual
            else:
                count = 0
                while count < limit:
                    parts = [keyword]
                    for k in selected_keys:
                        raw_val = random.choice(DATA_POOLS[k])
                        prefix = SHODAN_PREFIXES.get(k, "")
                        val = clean_value(raw_val)
                        if prefix:
                            part = f'{prefix}:{val}'
                        else:
                            part = f'{val}'
                        parts.append(part)
                    yield " ".join(parts)
                    count += 1
    
    # 2. GENERATE PURE AUTO QUERIES (NO MANUAL KEYWORD)
    else:
        if limit == 0:
            for combination in itertools.product(*lists_to_combine):
                parts = []
                for i, raw_val in enumerate(combination):
                    key_name = selected_keys[i]
                    prefix = SHODAN_PREFIXES.get(key_name, "")
                    val = clean_value(raw_val)
                    if prefix:
                        part = f'{prefix}:{val}'
                    else:
                        part = f'{val}'
                    parts.append(part)
                yield " ".join(parts)
        else:
            count = 0
            while count < limit:
                parts = []
                for k in selected_keys:
                    raw_val = random.choice(DATA_POOLS[k])
                    prefix = SHODAN_PREFIXES.get(k, "")
                    val = clean_value(raw_val)
                    if prefix:
                        part = f'{prefix}:{val}'
                    else:
                        part = f'{val}'
                    parts.append(part)
                yield " ".join(parts)
                count += 1

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    try:
        banner_text = pyfiglet.figlet_format("Raven X", font="slant")
        subtitle_text = pyfiglet.figlet_format("Multi-Target V7", font="digital")
    except:
        banner_text = "RAVEN X"
        subtitle_text = "Multi-Target V7"

    print(f"{Fore.CYAN}{Style.BRIGHT}{banner_text}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{subtitle_text}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'Created by @jimmybogartz | Multi-Input Injection'.center(60)}{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
    print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}High Quality Dataset Mode - Optimized for better results{Fore.RESET}")

    # Check if user wants to refresh datasets from Shodan
    if SHODAN_AVAILABLE and SHODAN_API_KEY != "YOUR_API_KEY_HERE":
        print(f"\n{Fore.CYAN}{Style.BRIGHT}[ DATASET REFRESH ]{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}[Y]{Fore.RESET} {Fore.WHITE}Refresh datasets from Shodan (get top items){Fore.RESET}")
        print(f"  {Fore.GREEN}[N]{Fore.RESET} {Fore.WHITE}Use cached/default datasets{Fore.RESET}")
        
        refresh_choice = input(f"\n{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Refresh datasets? (Y/N, default=N):{Fore.RESET} ").strip().upper()
        
        if refresh_choice == 'Y':
            top_n_input = input(f"{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Top N items per category? (default=100):{Fore.RESET} ").strip()
            try:
                top_n = int(top_n_input) if top_n_input else 100
                if top_n < 1:
                    top_n = 100
            except:
                top_n = 100
            
            # Initialize rate limiter untuk dataset refresh
            refresh_rate_limiter = RateLimiter(max_requests_per_minute=60, max_concurrent=2)
            
            update_datasets_from_shodan(
                SHODAN_API_KEY, 
                top_n=top_n, 
                force_refresh=True,
                rate_limiter_instance=refresh_rate_limiter
            )
            print(f"\n{Fore.GREEN}{Style.BRIGHT}[✓]{Style.RESET_ALL} {Fore.CYAN}Dataset refresh completed!{Fore.RESET}\n")
        else:
            # Load from cache if available (tidak perlu rate limiter untuk cache)
            update_datasets_from_shodan(SHODAN_API_KEY, force_refresh=False, rate_limiter_instance=None)
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}[ SELECT MODE ]{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}[1]{Fore.RESET} {Fore.WHITE}Auto Generator (Dataset vs Dataset){Fore.RESET}")
    print(f"  {Fore.GREEN}[2]{Fore.RESET} {Fore.WHITE}Multi-Manual Mixer (Inject list of keywords 1-by-1){Fore.RESET}")
    
    mode = input(f"\n{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Select Mode (1/2):{Fore.RESET} ").strip()
    
    manual_keywords_list = []
    output_basename = "raven_dorks"

    if mode == '2':
        print(f"{Fore.CYAN}{'-' * 60}{Fore.RESET}")
        print(f"{Fore.MAGENTA}{Style.BRIGHT}MULTI-MANUAL MODE{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Enter your keywords separated by comma.{Fore.RESET}")
        print(f"{Fore.BLUE}Example:{Fore.RESET} {Fore.YELLOW}product:\"gitlab\", product:\"bitbucket\", org:\"Tesla\"{Fore.RESET}")
        raw_manual_input = input(f"{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Enter Keywords:{Fore.RESET} ").strip()
        
        if not raw_manual_input:
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Keywords cannot be empty.{Fore.RESET}")
            return
        
        # Split by comma and clean whitespace
        manual_keywords_list = [x.strip() for x in raw_manual_input.split(',') if x.strip()]
        
        print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Loaded{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{len(manual_keywords_list)}{Style.RESET_ALL} {Fore.CYAN}unique keywords.{Fore.RESET}")
        
        # Set generic name + first keyword for filename
        first_key = sanitize_filename(manual_keywords_list[0])
        output_basename = f"raven_multi_{first_key}_etc"

    keys = list(DATA_POOLS.keys())
    print(f"\n{Fore.CYAN}{Style.BRIGHT}[ AVAILABLE DATASETS ]{Style.RESET_ALL}")
    for idx, k in enumerate(keys):
        count = len(DATA_POOLS[k])
        print(f"  {Fore.GREEN}[{idx+1}]{Fore.RESET} {Fore.CYAN}{k:<15}{Fore.RESET} {Fore.WHITE}({Fore.YELLOW}{count}{Fore.WHITE} items){Fore.RESET}")
    
    user_input = input(f"\n{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Select datasets indices (comma separated):{Fore.RESET} ").strip()
    
    if not user_input:
        print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Empty input. Exiting.{Fore.RESET}")
        return

    try:
        selected_indices = [int(x.strip()) - 1 for x in user_input.split(',')]
        selected_keys = []
        for i in selected_indices:
            if 0 <= i < len(keys):
                selected_keys.append(keys[i])
            else:
                print(f"{Fore.YELLOW}{Style.BRIGHT}[Warn]{Style.RESET_ALL} {Fore.YELLOW}Invalid index {i+1}, skipped.{Fore.RESET}")

        if not selected_keys:
            print(f"{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}No valid categories selected.{Fore.RESET}")
            return

        print(f"\n{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Selected Datasets:{Fore.RESET} {Fore.YELLOW}{' + '.join(selected_keys)}{Fore.RESET}")
        
        if mode == '1':
            keys_str = "_".join(selected_keys)
            output_basename = f"raven_{keys_str}"

        # Calculate Combinations
        dataset_combinations = 1
        for k in selected_keys:
            dataset_combinations *= len(DATA_POOLS[k])
        
        # Total = Datasets Combos * Number of Manual Keywords
        total_combinations = dataset_combinations
        if manual_keywords_list:
            total_combinations *= len(manual_keywords_list)
        
        print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL} {Fore.CYAN}Possible combinations:{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{total_combinations:,}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.CYAN}Note: Dataset telah dioptimasi untuk mengurangi kombinasi yang tidak relevan{Fore.RESET}")
        
        limit_input = input(f"{Fore.CYAN}{Style.BRIGHT}[?]{Style.RESET_ALL} {Fore.YELLOW}Output limit per keyword? (0 for ALL):{Fore.RESET} ").strip()
        try:
            limit = int(limit_input)
            if limit < 0: limit = 0
        except:
            limit = 0

        # Construct Dynamic Filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{output_basename}_{timestamp}.txt"

        print(f"\n{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Processing...{Fore.RESET} {Fore.WHITE}(Output:{Fore.RESET} {Fore.YELLOW}{output_filename}{Fore.WHITE}){Fore.RESET}")
        
        start_time = time.time()
        count = 0
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            for query in generate_queries(selected_keys, limit, manual_keywords_list):
                f.write(query + "\n")
                count += 1
                
                if count % 500 == 0:
                    sys.stdout.write(f"\r    {Fore.CYAN}Generated:{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{count:,}{Style.RESET_ALL} {Fore.WHITE}queries...{Fore.RESET}")
                    sys.stdout.flush()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n\n{Fore.GREEN}{Style.BRIGHT}[SUCCESS]{Style.RESET_ALL} {Fore.CYAN}Completed in{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{duration:.2f}{Style.RESET_ALL} {Fore.CYAN}seconds.{Fore.RESET}")
        print(f"{Fore.BLUE}{Style.BRIGHT}[INFO]{Style.RESET_ALL} {Fore.CYAN}Total{Fore.RESET} {Fore.GREEN}{Style.BRIGHT}{count:,}{Style.RESET_ALL} {Fore.CYAN}queries saved in{Fore.RESET} {Fore.YELLOW}'{output_filename}'{Fore.RESET}")
        
        print(f"{Fore.CYAN}{'-' * 60}{Fore.RESET}")
        print(f"{Fore.MAGENTA}{Style.BRIGHT}PREVIEW:{Style.RESET_ALL}")
        try:
            with open(output_filename, 'r') as f:
                for _ in range(5):
                    line = f.readline().strip()
                    if line:
                        print(f"{Fore.WHITE} >{Fore.RESET} {Fore.CYAN}{line}{Fore.RESET}")
        except:
            pass
        print(f"{Fore.CYAN}{'-' * 60}{Fore.RESET}")
        
        # Auto-run facet check and download (FULLY AUTOMATIC)
        if SHODAN_AVAILABLE and SHODAN_API_KEY != "YOUR_API_KEY_HERE":
            print(f"\n{Fore.MAGENTA}{Style.BRIGHT}[ FACET & AUTO-DOWNLOAD ]{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {Fore.CYAN}Starting automatic facet check and download...{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL} {Fore.CYAN}Configuration:{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Facet threshold:{Fore.RESET} {Fore.YELLOW}> 0{Fore.RESET} {Fore.WHITE}(download all facets with count > 0){Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Threads:{Fore.RESET} {Fore.YELLOW}4{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Limit per query:{Fore.RESET} {Fore.YELLOW}100000000{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Filter after:{Fore.RESET} {Fore.YELLOW}2024-01-01{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Rate limit:{Fore.RESET} {Fore.YELLOW}60{Fore.RESET} {Fore.WHITE}requests/minute{Fore.RESET}")
            print(f"{Fore.BLUE}{Style.BRIGHT}[i]{Style.RESET_ALL}   {Fore.WHITE}- Max concurrent:{Fore.RESET} {Fore.YELLOW}3{Fore.RESET}")
            
            print(f"\n{Fore.CYAN}{'='*60}{Fore.RESET}")
            run_facet_and_download(
                output_filename, 
                SHODAN_API_KEY, 
                "2024-01-01", 
                100000000, 
                4, 
                facet_threshold=0,
                max_requests_per_minute=60,  # Rate limit: 60 requests per minute
                max_concurrent=3  # Max 3 concurrent API calls
            )
            print(f"{Fore.CYAN}{'='*60}{Fore.RESET}")
        elif SHODAN_AVAILABLE:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Shodan API Key not set. Set SHODAN_API_KEY in script to enable auto-download.{Fore.RESET}")

    except ValueError:
        print(f"\n{Fore.RED}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.RED}Error:{Fore.RESET} {Fore.YELLOW}Invalid input format.{Fore.RESET}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {Fore.YELLOW}Process cancelled.{Fore.RESET}")

if __name__ == "__main__":
    main()
