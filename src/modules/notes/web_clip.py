"""Bounded, synchronous webpage extraction. Browser dependencies are optional."""
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
import base64
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

WEB_METHOD_AUTO = 0
WEB_METHOD_READER = 1
WEB_METHOD_RENDERED = 2
WEB_METHOD_ARCHIVE = 4
METHOD_LABELS = {0: "Auto", 1: "Reader / Article Extract", 2: "Rendered Page", 4: "Web Archive"}
MAX_HTML = 20 * 1024 * 1024
ARCHIVE_LOAD_MS = 20000
ARCHIVE_CAPTURE_MS = 45000
ARCHIVE_PROCESS_SECONDS = 75
IMAGE_RE = re.compile(r'!\[([^\]\n]*)\]\((<?[^\s)]+>?)(?:\s+"[^"]*")?\)')
log = logging.getLogger(__name__)


class WebClipError(ValueError):
    """A message safe to display in the UI."""


@dataclass
class WebClipResult:
    success: bool = False
    method_used: int = 1
    source_url: str = ""
    final_url: str = ""
    title: str = ""
    author: str = ""
    published_date: str = ""
    markdown: str = ""
    html: str = ""
    site_name: str = ""
    images: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    captured: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def validate_url(url):
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
        raise WebClipError("Enter a valid HTTP or HTTPS webpage URL.")
    url = url.strip()
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError()
        _ = parts.port
    except ValueError:
        raise WebClipError("Enter a valid HTTP or HTTPS webpage URL.") from None
    return url


def url_key(url):
    p = urlsplit(validate_url(url))
    # Preserve path case and query parameters, which can identify different pages.
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.query, ""))


def fetch_bytes(url, limit=MAX_HTML, timeout=20):
    import requests
    started = time.monotonic()
    try:
        with requests.get(validate_url(url), timeout=(5, timeout), stream=True,
                          headers={"User-Agent": "LifePIM Webpage Notes/1.0"}) as response:
            if response.status_code >= 400:
                raise WebClipError(f"The webpage returned HTTP {response.status_code}.")
            final_url = validate_url(response.url)
            chunks = bytearray()
            for chunk in response.iter_content(65536):
                chunks.extend(chunk)
                if len(chunks) > limit:
                    raise WebClipError("The webpage or image exceeds the download size limit.")
                if time.monotonic() - started > timeout:
                    raise WebClipError("The webpage download timed out.")
            return bytes(chunks), final_url
    except requests.RequestException as exc:
        log.info("Webpage request failed", exc_info=True)
        raise WebClipError("Could not connect to webpage.") from exc


def is_web_content_useful(markdown, title="", structured=False):
    text = re.sub(r'[#*_`\[\]()>]', '', markdown or '').strip()
    paragraphs = [p for p in text.split("\n") if len(p.strip()) >= 30]
    link_text = sum(len(m) for m in re.findall(r'\[[^\]]*\]\([^)]*\)', markdown or ''))
    boilerplate = sum(text.lower().count(word) for word in ("accept cookies", "sign in", "subscribe", "privacy policy"))
    if boilerplate > 2 and len(text) < 500:
        return False
    if link_text > len(markdown or '') * .7:
        return False
    return bool(paragraphs and (len(text) >= 200 or (structured and title and len(text) >= 60)))


def _recipe_content(tree, url, page_title):
    """Read public schema.org Recipe data, including content hidden by 'read more'.

    Article extractors often discard ingredient lists and short instruction blocks.
    This uses the site's published structured data, without site-specific selectors.
    """
    from lxml import html as lhtml
    from html import escape, unescape

    def text(value):
        if not isinstance(value, (str, int, float)):
            return ''
        fragment = lhtml.fragment_fromstring(str(value), create_parent='div')
        for element in fragment.xpath('.//script|.//style'):
            element.drop_tree()
        return escape(' '.join(fragment.text_content().split()), quote=False)

    def steps(value, depth=0):
        if depth > 15:
            return []
        if isinstance(value, list):
            return [step for item in value for step in steps(item, depth + 1)]
        if isinstance(value, dict):
            children = value.get('itemListElement')
            if children:
                heading = text(value.get('name'))
                return ([('section', heading)] if heading else []) + steps(children, depth + 1)
            content = text(value.get('text') or value.get('name'))
            return [('step', content)] if content else []
        if isinstance(value, str):
            fragment = lhtml.fragment_fromstring(value, create_parent='div')
            lines = [element.text_content() for element in fragment.xpath('.//li')]
            return [('step', text(line)) for line in (lines or value.splitlines()) if text(line)]
        return []

    candidates = []
    for script in tree.xpath('//script[translate(@type,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="application/ld+json"]/text()'):
        try:
            pending = [json.loads(script)]
        except (ValueError, RecursionError):
            continue
        visited = 0
        while pending and visited < 10000:
            node = pending.pop()
            visited += 1
            if isinstance(node, list):
                pending.extend(reversed(node))
            elif isinstance(node, dict):
                types = node.get('@type', [])
                types = types if isinstance(types, list) else [types]
                if any(str(kind).rstrip('/').rsplit('/', 1)[-1].rsplit(':', 1)[-1] == 'Recipe' for kind in types):
                    ingredients = node.get('recipeIngredient')
                    if isinstance(ingredients, str):
                        ingredients = ingredients.splitlines()
                    if isinstance(ingredients, list):
                        ingredients = [text(item) for item in ingredients if isinstance(item, str) and text(item)]
                        method = steps(node.get('recipeInstructions'))
                        if ingredients and any(kind == 'step' for kind, _ in method):
                            candidates.append((node, ingredients, method))
                pending.extend(reversed(list(node.values())))
    if not candidates:
        return None
    def title_key(value):
        return re.sub(r'\W+', '', str(value).casefold())
    candidates.sort(key=lambda item: title_key(item[0].get('name')) == title_key(page_title), reverse=True)
    recipe, ingredients, method = candidates[0]
    title = unescape(text(recipe.get('name'))) or page_title
    parts = []
    description = text(recipe.get('description'))
    if description:
        parts.append(description)
    for label, key in [('Servings', 'recipeYield'), ('Prep time', 'prepTime'), ('Cook time', 'cookTime'), ('Total time', 'totalTime')]:
        value = recipe.get(key)
        if isinstance(value, list):
            value = ', '.join(str(item) for item in value if isinstance(item, (str, int)))
        value = text(value)
        if value:
            # ISO 8601 durations are common recipe metadata; make them readable.
            duration = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value)
            if duration:
                value = ' '.join(f'{n} {unit}' for n, unit in zip(duration.groups(), ('hr', 'min', 'sec')) if n)
            parts.append(f'{label}: {value}')
    image = recipe.get('image', [])
    image = image if isinstance(image, list) else [image]
    images = []
    for item in image:
        source = item.get('url') or item.get('contentUrl') if isinstance(item, dict) else item
        if isinstance(source, str):
            source = urljoin(url, source)
            if urlsplit(source).scheme in {'http', 'https'}:
                images.append(source)
                parts.append(f'![Recipe image]({source})')
                break  # Multiple image sizes usually refer to the same photograph.
    parts += ['## Ingredients', '\n'.join(f'- {item}' for item in ingredients), '## Method']
    number = 0
    for kind, value in method:
        if kind == 'section':
            parts.append(f'### {value}')
        else:
            number += 1
            parts.append(f'{number}. {value}')
    author = recipe.get('author', '')
    author = author if isinstance(author, list) else [author]
    author = ', '.join(text(item.get('name') if isinstance(item, dict) else item) for item in author)
    return WebClipResult(success=True, title=title, markdown='\n\n'.join(parts), author=unescape(author),
                         published_date=text(recipe.get('datePublished')), images=images)


def extract_html(html, url, method):
    try:
        import trafilatura
        from lxml import html as lhtml
    except ImportError as exc:
        raise WebClipError("Reader support is not installed. Install the application requirements.") from exc
    tree = lhtml.fromstring(html)
    tree.make_links_absolute(url)
    for element in tree.xpath('//*[@href or @src]'):
        for attribute in ('href', 'src'):
            target = element.get(attribute)
            if target and urlsplit(target).scheme.lower() not in {'http', 'https', 'mailto', 'data'}:
                element.attrib.pop(attribute, None)
    structured = bool(tree.xpath('//article|//main'))
    metadata = trafilatura.extract_metadata(tree, default_url=url)
    title = (metadata.title if metadata else "") or ""
    try:
        recipe = _recipe_content(tree, url, title)
    except Exception:
        log.debug('Ignoring unusable recipe metadata', exc_info=True)
        recipe = None
    body = trafilatura.extract(tree, url=url, output_format="markdown", include_comments=False,
                               include_tables=True, include_links=True, include_images=True,
                               include_formatting=True, favor_precision=True) or ""
    # Literal HTML quoted by an article must remain text in ordinary Notes views.
    body = body.replace('<', '&lt;').replace('>', '&gt;')
    result = WebClipResult(method_used=method, source_url=url, final_url=url, title=title,
                           markdown=body, site_name=urlsplit(url).hostname or "")
    if metadata:
        result.author = metadata.author or ""
        result.published_date = metadata.date or ""
        result.site_name = metadata.sitename or result.site_name
    if recipe:
        result.title = title = recipe.title
        result.author = recipe.author or result.author
        result.published_date = recipe.published_date or result.published_date
        # The structured recipe is authoritative; retain genuinely separate article
        # content (such as cooking tips), without duplicating a recipe already extracted.
        if body and not re.search(r'(?im)^#{1,6}\s+(?:ingredients|method|instructions)\b', body):
            recipe.markdown += '\n\n## More from this page\n\n' + body
        body = result.markdown = recipe.markdown
    result.success = bool(recipe) or is_web_content_useful(body, title, structured)
    result.images = list(dict.fromkeys(m.group(2).strip('<>') for m in IMAGE_RE.finditer(body)))
    if not result.success:
        result.warnings.append(f"{METHOD_LABELS[method]} could not identify useful page content.")
    result.title = title or urlsplit(url).hostname or "Webpage"
    return result


def extract_reader(url):
    html, final = fetch_bytes(url)
    result = extract_html(html, final, WEB_METHOD_READER)
    result.source_url = url
    return result


def extract_rendered(url):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    except ImportError as exc:
        raise WebClipError("Rendered Page support is not installed.") from exc
    try:
        with sync_playwright() as pw:
            with pw.chromium.launch(headless=True) as browser:
                page = browser.new_page()
                # Local HTTP sites are allowed; other resource schemes are not navigations.
                response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
                if response and response.status >= 400:
                    if response.status in {401, 403}:
                        raise WebClipError(f"Rendered Page was refused by the website (HTTP {response.status}). Try Reader / Article Extract or Web Archive.")
                    raise WebClipError(f"The webpage returned HTTP {response.status}.")
                page.wait_for_timeout(1500)
                final = validate_url(page.url)
                html = page.content()
                if len(html.encode('utf-8')) > MAX_HTML:
                    raise WebClipError("The rendered webpage exceeds the size limit.")
        result = extract_html(html, final, WEB_METHOD_RENDERED)
        result.source_url = url
        return result
    except BrowserTimeout as exc:
        raise WebClipError("Rendered page timed out.") from exc
    except WebClipError:
        raise
    except Exception as exc:
        raise WebClipError("Could not render webpage. Check that Playwright Chromium is installed.") from exc


def _archive_browser_args():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            # Complete a driver round-trip before closing; merely reading executable_path
            # can leave Playwright's asynchronous startup pending on Windows.
            context = pw.request.new_context()
            context.dispose()
            browser_path = pw.chromium.executable_path
            if Path(browser_path).is_file():
                return ['--browser-executable-path', browser_path]
    except Exception:
        # SingleFile can discover a system Chrome even without Playwright.
        log.debug('No Playwright browser available for SingleFile', exc_info=True)
    return []


def _run_archive(command):
    windows = os.name == 'nt'
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                          start_new_session=not windows) as process:
        try:
            _, stderr = process.communicate(timeout=ARCHIVE_PROCESS_SECONDS)
        except subprocess.TimeoutExpired:
            # Stop the browser children too, before the temporary directory is cleaned.
            try:
                if windows:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            finally:
                process.kill()
                process.communicate()
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stderr=stderr)


def archive_webpage(url):
    executable = shutil.which("single-file")
    bundled = Path(sys.executable).with_name('single-file.exe' if os.name == 'nt' else 'single-file')
    if not executable and bundled.is_file():
        executable = str(bundled)
    if not executable:
        raise WebClipError("Web Archive support is not installed.")
    # npm Windows shims would invoke cmd.exe with URL text; resolve to node instead.
    command = [executable]
    if Path(executable).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        script = Path(executable).parent / 'node_modules/single-file-cli/single-file-node.js'
        node = shutil.which('node')
        if not node or not script.is_file():
            raise WebClipError("Install the standalone SingleFile executable for Web Archive support.")
        command = [node, str(script)]
    command += _archive_browser_args()
    # Busy advertising/analytics requests may never become idle. Give navigation and
    # capture separate budgets that fit inside the outer process deadline.
    command += ['--browser-single-process', 'false',
                '--browser-wait-until', 'domContentLoaded',
                '--browser-wait-delay', '1500',
                '--browser-load-max-time', str(ARCHIVE_LOAD_MS),
                '--browser-capture-max-time', str(ARCHIVE_CAPTURE_MS),
                '--remove-frames', 'true',
                '--load-deferred-images', 'false']
    with tempfile.TemporaryDirectory(prefix="lifepim-web-") as tmp:
        output = Path(tmp) / "page.html"
        try:
            _run_archive(command + [url, str(output)])
            if output.stat().st_size > MAX_HTML:
                raise WebClipError("The archived webpage exceeds the size limit.")
            html = output.read_text(encoding="utf-8")
            if not html.strip():
                raise WebClipError("Web Archive did not produce a usable snapshot.")
        except subprocess.TimeoutExpired as exc:
            raise WebClipError("Web Archive timed out.") from exc
        except subprocess.CalledProcessError as exc:
            diagnostic = (exc.stderr or b'').decode('utf-8', errors='replace') if isinstance(exc.stderr, bytes) else str(exc.stderr or '')
            log.warning('SingleFile failed (exit %s): %s', exc.returncode, diagnostic[-2000:])
            if 'capture timeout' in diagnostic.lower():
                raise WebClipError("Web Archive timed out while collecting page resources.") from exc
            if 'load timeout' in diagnostic.lower():
                raise WebClipError("Web Archive timed out while loading the webpage.") from exc
            raise WebClipError("Could not archive webpage.") from exc
        except OSError as exc:
            raise WebClipError("Could not archive webpage.") from exc
    final_url = url
    saved_url = re.search(r'Page saved with SingleFile\s+url:\s*(\S+)', html[:8192])
    if saved_url:
        try:
            final_url = validate_url(saved_url.group(1))
        except WebClipError:
            pass
    try:
        result = extract_html(html, final_url, WEB_METHOD_ARCHIVE)
    except Exception:
        log.info("Archive article extraction failed", exc_info=True)
        result = WebClipResult(method_used=4, source_url=url, final_url=url, title=urlsplit(url).hostname)
    if not result.success:
        result.markdown = "The webpage was archived but readable article content could not be automatically extracted."
        result.warnings.append("Saved archive; readable article content could not be extracted.")
    result.success = True
    result.source_url = url
    result.final_url = final_url
    result.html = html
    result.warnings.append('The archive omits embedded frames and images that require scrolling to load.')
    return result


def fetch_web_note(url, method=WEB_METHOD_AUTO):
    url = validate_url(url)
    if type(method) is not int or method not in METHOD_LABELS:
        raise WebClipError("Choose a supported extraction method.")
    warnings = []
    # Explicit order: Reader, then browser rendering, then standalone archive.
    methods = [1, 2, 4] if method == 0 else [method]
    adapters = {1: extract_reader, 2: extract_rendered, 4: archive_webpage}
    for selected in methods:
        started = time.monotonic()
        try:
            result = adapters[selected](url)
        except WebClipError as exc:
            log.info("WEB_CLIP_METHOD_FAILED method=%s url=%s", selected, url, exc_info=True)
            result = WebClipResult(method_used=selected, source_url=url, warnings=[str(exc)])
        except Exception:
            log.exception("WEB_CLIP_METHOD_FAILED method=%s url=%s", selected, url)
            result = WebClipResult(method_used=selected, source_url=url,
                                   warnings=[f"{METHOD_LABELS[selected]} could not extract this webpage."])
        result.warnings = warnings + result.warnings
        log.info("WEB_CLIP_STAGE method=%s seconds=%.2f success=%s chars=%s images=%s",
                 selected, time.monotonic() - started, result.success, len(result.markdown), len(result.images))
        if result.success:
            result.source_url = url
            heading = result.title.replace('<', '&lt;').replace('>', '&gt;')
            body = result.markdown.strip()
            first, _, remainder = body.partition('\n')
            if first.lstrip('# ').strip().casefold() == heading.casefold():
                body = remainder.lstrip()
            result.markdown = f"# {heading}\n\n{body}\n\n---\n\nSource: {url}\nCaptured: {result.captured[:10]}\n"
            return result
        warnings = result.warnings
    return result


def filename_for(result, max_length=220):
    def slug(value):
        return re.sub(r'_+', '_', re.sub(r'[^a-z0-9]', '_', value.lower())).strip('_')
    host = (urlsplit(result.source_url).hostname or 'webpage').removeprefix('www.')
    prefix = f"web_snip_{slug(host)[:80]}_"
    suffix = f"_{result.captured[:10].replace('-', '')}.md"
    budget = max_length - len(prefix) - len(suffix)
    if budget < 8:
        raise WebClipError("The default Notes folder path is too long for a webpage filename.")
    return prefix + (slug(result.title) or 'page')[:budget].rstrip('_') + suffix


def download_images(markdown, result, assets):
    """Download only extracted article images still present after the user's edits."""
    from PIL import Image
    warnings = []
    downloaded = {}
    allowed = set(result.images)
    started = time.monotonic()
    for match in IMAGE_RE.finditer(markdown):
        source = match.group(2).strip('<>')
        if source not in allowed or source in downloaded:
            continue
        if len(downloaded) >= 20 or time.monotonic() - started > 30:
            warnings.append("Some article images were left as remote references (download limit).")
            break
        if re.search(r'(tracking|pixel|favicon|doubleclick|/ads/)', source, re.I):
            continue
        try:
            if source.startswith('data:image/') and ';base64,' in source:
                encoded = source.split(';base64,', 1)[1]
                if len(encoded) > 11 * 1024 * 1024:
                    raise WebClipError('The embedded image exceeds the size limit.')
                payload = base64.b64decode(encoded, validate=True)
            else:
                payload, _ = fetch_bytes(urljoin(result.final_url, source), limit=8 * 1024 * 1024, timeout=8)
            with Image.open(BytesIO(payload)) as img:
                if min(img.size) < 64:
                    continue
                extension = {'JPEG': '.jpg', 'PNG': '.png', 'GIF': '.gif', 'WEBP': '.webp'}.get(img.format)
                img.verify()
            if not extension:
                continue
            assets.mkdir(exist_ok=True)
            target = assets / f"image_{len(downloaded) + 1:03d}{extension}"
            target.write_bytes(payload)
            downloaded[source] = f"{assets.name}/{target.name}"
        except Exception:
            log.info("Article image download failed", exc_info=True)
            warnings.append("An article image could not be downloaded; its original reference was kept.")
    return IMAGE_RE.sub(lambda m: m.group(0).replace(m.group(2), downloaded.get(m.group(2).strip('<>'), m.group(2))), markdown), warnings
