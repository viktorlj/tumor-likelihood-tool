# AACR GENIE Attribution Footer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent footer to every page crediting AACR Project GENIE as the data source, with logo and links to the homepage and 2017 *Cancer Discovery* manuscript.

**Architecture:** A new Jinja partial `templates/partials/footer.html` is included after `</main>` in all four existing templates (`index.html`, `tumor_profile.html`, `gene_profile.html`, `tutorial.html`). The GENIE logo is downloaded once to `static/genie-logo.jpeg` and served locally. Footer CSS lives in `static/profile.css` (same file that already owns `.mp-nav` chrome rules).

**Tech Stack:** FastAPI + Jinja2 templates, vanilla CSS, pytest + FastAPI `TestClient` for integration testing.

**Spec:** `docs/superpowers/specs/2026-04-09-aacr-genie-attribution-footer-design.md`

---

## File Structure

**New files:**
- `templates/partials/footer.html` — the footer partial (single responsibility: render attribution block)
- `static/genie-logo.jpeg` — downloaded logo asset, served as a static file
- `tests/test_footer.py` — integration test verifying footer is rendered on all four HTML pages

**Modified files:**
- `templates/index.html` — add `{% include 'partials/footer.html' %}` after `</main>`
- `templates/tumor_profile.html` — add `{% include 'partials/footer.html' %}` after `</main>`
- `templates/gene_profile.html` — add `{% include 'partials/footer.html' %}` after `</main>`
- `templates/tutorial.html` — add `{% include 'partials/footer.html' %}` after `</main>`
- `static/profile.css` — append `.mp-footer*` rules and a responsive wrap rule

---

## Task 1: Write failing integration tests for footer presence

**Files:**
- Create: `tests/test_footer.py`

Tests hit each HTML route through `TestClient` and assert the response body contains the GENIE logo image, homepage link, and manuscript DOI link. This proves the footer renders on every page.

- [ ] **Step 1: Create the failing test file**

Create `tests/test_footer.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.scoring import TumorLikelihoodModel


HTML_ROUTES = ["/", "/tumor-profile", "/gene-profile", "/tutorial"]
GENIE_HOMEPAGE_URL = "https://genie.synapse.org/"
GENIE_MANUSCRIPT_DOI = "https://doi.org/10.1158/2159-8290.CD-17-0151"
GENIE_LOGO_SRC = "/static/genie-logo.jpeg"


@pytest.fixture()
def client(synthetic_data_dir):
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    app = create_app(data_dir=synthetic_data_dir, model=model)
    return TestClient(app)


@pytest.mark.parametrize("route", HTML_ROUTES)
def test_footer_renders_on_every_page(client, route):
    response = client.get(route)
    assert response.status_code == 200
    body = response.text
    assert 'class="mp-footer"' in body, f"footer container missing on {route}"
    assert GENIE_LOGO_SRC in body, f"GENIE logo missing on {route}"
    assert GENIE_HOMEPAGE_URL in body, f"GENIE homepage link missing on {route}"
    assert GENIE_MANUSCRIPT_DOI in body, f"GENIE manuscript link missing on {route}"


def test_footer_logo_asset_is_served(client):
    response = client.get(GENIE_LOGO_SRC)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:
```bash
source .venv/bin/activate && pytest tests/test_footer.py -v
```

Expected: All 5 tests FAIL. The parametrized tests fail because `class="mp-footer"` is not in any page yet. The asset test fails with a 404 because `static/genie-logo.jpeg` does not exist.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_footer.py
git commit -m "test: add footer attribution tests (currently failing)"
```

---

## Task 2: Download the GENIE logo asset

**Files:**
- Create: `static/genie-logo.jpeg`

The user-provided URL points to a hashed Synapse asset (`GENIE-logo-D5F_ywVl.jpeg`) that may rotate. Downloading once and serving locally is standard attribution practice: host the asset, link back to the source.

- [ ] **Step 1: Download the logo to `static/genie-logo.jpeg`**

Run:
```bash
curl -fsSL "https://genie.synapse.org/assets/GENIE-logo-D5F_ywVl.jpeg" \
  -o static/genie-logo.jpeg
```

- [ ] **Step 2: Verify the file is a valid JPEG**

Run:
```bash
file static/genie-logo.jpeg
```

Expected output contains `JPEG image data`. The file should be non-empty (a few KB at minimum).

- [ ] **Step 3: Rerun just the asset test and verify it passes**

Run:
```bash
source .venv/bin/activate && pytest tests/test_footer.py::test_footer_logo_asset_is_served -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add static/genie-logo.jpeg
git commit -m "feat: add AACR GENIE logo asset"
```

---

## Task 3: Create the footer partial template

**Files:**
- Create: `templates/partials/footer.html`

- [ ] **Step 1: Create the footer partial**

Create `templates/partials/footer.html`:

```html
<footer class="mp-footer">
  <div class="mp-footer-inner">
    <a
      href="https://genie.synapse.org/"
      target="_blank"
      rel="noopener"
      class="mp-footer-logo-link"
    >
      <img
        src="/static/genie-logo.jpeg"
        alt="AACR Project GENIE"
        class="mp-footer-logo"
      />
    </a>
    <div class="mp-footer-text">
      <p class="mp-footer-credit">
        Powered by data from the
        <a href="https://genie.synapse.org/" target="_blank" rel="noopener">AACR Project GENIE</a>
        consortium.
      </p>
      <p class="mp-footer-links">
        <a href="https://genie.synapse.org/" target="_blank" rel="noopener">Homepage</a>
        <span class="mp-footer-sep">·</span>
        <a
          href="https://doi.org/10.1158/2159-8290.CD-17-0151"
          target="_blank"
          rel="noopener"
          >Manuscript (Cancer Discovery, 2017)</a
        >
      </p>
    </div>
  </div>
</footer>
```

Note: the partial is not yet included by any page, so the page-level tests still fail. That's expected — the include step is next.

- [ ] **Step 2: Commit**

```bash
git add templates/partials/footer.html
git commit -m "feat: add GENIE attribution footer partial"
```

---

## Task 4: Include the footer on `index.html`

**Files:**
- Modify: `templates/index.html` (insert after line 71, i.e. after `</main>`)

- [ ] **Step 1: Add the include directly after `</main>`**

Change `templates/index.html` from:

```html
      <section class="mp-panel results-panel mp-hidden" id="results-panel">
        <div id="confidence-banner" class="mp-alert mp-hidden"></div>
        <div id="notes" class="notes mp-soft"></div>
        <div id="results-tumor" class="result-list"></div>
      </section>
    </main>

    <template id="mutation-row-template">
```

to:

```html
      <section class="mp-panel results-panel mp-hidden" id="results-panel">
        <div id="confidence-banner" class="mp-alert mp-hidden"></div>
        <div id="notes" class="notes mp-soft"></div>
        <div id="results-tumor" class="result-list"></div>
      </section>
    </main>

    {% include 'partials/footer.html' %}

    <template id="mutation-row-template">
```

- [ ] **Step 2: Run the parametrized test for `/` and verify it passes**

Run:
```bash
source .venv/bin/activate && pytest "tests/test_footer.py::test_footer_renders_on_every_page[/]" -v
```

Expected: PASS. The three other parametrized cases still fail — that's fine, they're fixed in Tasks 5–7.

---

## Task 5: Include the footer on `tumor_profile.html`

**Files:**
- Modify: `templates/tumor_profile.html` (insert after line 91, i.e. after `</main>`)

- [ ] **Step 1: Add the include directly after `</main>`**

Change `templates/tumor_profile.html` from:

```html
          <div class="empty-state"><p>Loading...</p></div>
        </div>
      </section>
    </main>

    <script src="/static/tumor-profile.js" defer></script>
  </body>
```

to:

```html
          <div class="empty-state"><p>Loading...</p></div>
        </div>
      </section>
    </main>

    {% include 'partials/footer.html' %}

    <script src="/static/tumor-profile.js" defer></script>
  </body>
```

- [ ] **Step 2: Run the parametrized test for `/tumor-profile` and verify it passes**

Run:
```bash
source .venv/bin/activate && pytest "tests/test_footer.py::test_footer_renders_on_every_page[/tumor-profile]" -v
```

Expected: PASS.

---

## Task 6: Include the footer on `gene_profile.html`

**Files:**
- Modify: `templates/gene_profile.html` (insert after line 94, i.e. after `</main>`)

- [ ] **Step 1: Add the include directly after `</main>`**

Change `templates/gene_profile.html` from:

```html
        <div id="tab-cna" class="tab-panel">
          <div class="empty-state"><p>Loading...</p></div>
        </div>
      </section>
    </main>

    <script src="/static/gene-profile.js" defer></script>
```

to:

```html
        <div id="tab-cna" class="tab-panel">
          <div class="empty-state"><p>Loading...</p></div>
        </div>
      </section>
    </main>

    {% include 'partials/footer.html' %}

    <script src="/static/gene-profile.js" defer></script>
```

- [ ] **Step 2: Run the parametrized test for `/gene-profile` and verify it passes**

Run:
```bash
source .venv/bin/activate && pytest "tests/test_footer.py::test_footer_renders_on_every_page[/gene-profile]" -v
```

Expected: PASS.

---

## Task 7: Include the footer on `tutorial.html`

**Files:**
- Modify: `templates/tutorial.html` (insert after line 430, i.e. after `</main>`)

- [ ] **Step 1: Add the include directly after `</main>`**

Change `templates/tutorial.html` from:

```html
          </ol>
        </div>
      </section>
    </main>
  </body>
```

to:

```html
          </ol>
        </div>
      </section>
    </main>

    {% include 'partials/footer.html' %}
  </body>
```

- [ ] **Step 2: Run the full footer test module and verify all tests pass**

Run:
```bash
source .venv/bin/activate && pytest tests/test_footer.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 3: Commit all four template changes together**

```bash
git add templates/index.html templates/tumor_profile.html templates/gene_profile.html templates/tutorial.html
git commit -m "feat: include GENIE footer on all page templates"
```

---

## Task 8: Add footer CSS

**Files:**
- Modify: `static/profile.css` (append new rules at the end, before or after the existing `@media (max-width: 700px)` block)

The `.mp-nav` rules already live in `profile.css` — the new `.mp-footer*` rules join them to keep chrome CSS together. Styles reuse the existing `--mp-*` tokens from `molpath.css` so the footer matches the site aesthetic.

- [ ] **Step 1: Append the new footer rules to `static/profile.css`**

Open `static/profile.css`. Before the final closing `}` of the existing `@media (max-width: 700px) { ... }` block (currently at line 330), add new rules *above* the `@media` block, then add responsive rules *inside* the existing `@media` block.

First, append these rules above line 286 (before the `/* Responsive */` comment header):

```css
/* =================================================================
   Footer (AACR GENIE attribution)
   ================================================================= */

.mp-footer {
  margin-top: 40px;
  padding: 18px 20px;
  background: var(--mp-panel);
  border-top: 1px solid var(--mp-border);
}

.mp-footer-inner {
  display: flex;
  align-items: center;
  gap: 18px;
  max-width: 1200px;
  margin: 0 auto;
}

.mp-footer-logo-link {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.mp-footer-logo {
  height: 48px;
  width: auto;
  display: block;
}

.mp-footer-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--mp-ink-soft);
  font-size: 0.82rem;
  line-height: 1.4;
}

.mp-footer-text p {
  margin: 0;
}

.mp-footer-credit a,
.mp-footer-links a {
  color: var(--mp-accent);
  text-decoration: none;
}

.mp-footer-credit a:hover,
.mp-footer-links a:hover {
  color: var(--mp-accent-hover);
  text-decoration: underline;
}

.mp-footer-sep {
  margin: 0 6px;
  color: var(--mp-border);
}
```

Second, add these rules inside the existing `@media (max-width: 700px) { ... }` block, immediately before its closing `}`:

```css
  .mp-footer-inner {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .mp-footer-logo {
    height: 40px;
  }
```

- [ ] **Step 2: Rerun the full footer test module (CSS changes must not break anything)**

Run:
```bash
source .venv/bin/activate && pytest tests/test_footer.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add static/profile.css
git commit -m "feat: style AACR GENIE attribution footer"
```

---

## Task 9: Full test sweep and manual browser verification

Catches any regression introduced in the other test modules and gives a visual sanity check before marking the feature done.

- [ ] **Step 1: Run the full test suite**

Run:
```bash
source .venv/bin/activate && pytest -v
```

Expected: All tests PASS, including the pre-existing `test_api.py`, `test_parser.py`, `test_profile_api.py`, `test_scoring.py` modules.

- [ ] **Step 2: Start the dev server and visually verify**

Run (in a separate terminal or foreground):
```bash
source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

Open each of the following in a browser and confirm the footer renders at the bottom of the page with (a) the GENIE logo on the left, (b) the credit line and both links on the right, (c) no layout breakage:

- `http://localhost:8000/`
- `http://localhost:8000/tumor-profile`
- `http://localhost:8000/gene-profile`
- `http://localhost:8000/tutorial`

Then resize the browser window to < 700px wide and confirm the footer wraps to a stacked layout (logo on top, text below) without overflowing.

Click each of the three footer links in turn (logo, "Homepage", "Manuscript") and confirm they open in a new tab with the expected destination:
- Logo → `https://genie.synapse.org/`
- Homepage → `https://genie.synapse.org/`
- Manuscript → `https://doi.org/10.1158/2159-8290.CD-17-0151`

- [ ] **Step 3: Stop the dev server (Ctrl+C)**

- [ ] **Step 4: No commit needed for verification** — all changes were already committed in previous tasks.
