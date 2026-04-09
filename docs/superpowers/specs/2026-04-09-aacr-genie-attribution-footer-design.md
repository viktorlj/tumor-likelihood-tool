# AACR GENIE Attribution Footer — Design

**Date:** 2026-04-09
**Status:** Approved, ready for implementation plan

## Motivation

The tumor likelihood tool is built entirely on data from the AACR Project
GENIE consortium. The consortium asks downstream users to credit GENIE and
link to their manuscript. The current UI mentions "AACR GENIE Inference" as
a hero eyebrow on the landing page but does not provide a visible link,
logo, or citation. This spec adds a persistent, understated footer
providing proper attribution across every page.

## Goals

- Credit AACR Project GENIE as the data source on every page.
- Link to the GENIE homepage (`https://genie.synapse.org/`).
- Cite the canonical 2017 *Cancer Discovery* paper
  (DOI: `10.1158/2159-8290.CD-17-0151`).
- Display the official GENIE logo.
- Match the existing minimalist "molpath" visual aesthetic.

## Non-Goals

- No new navigation entries or pages.
- No changes to the hero, forms, or results panels.
- No behavioral / JavaScript changes.
- No changes to data loading, scoring, or API logic.

## Design

### Placement

A footer is rendered at the bottom of every page, after `</main>` and
before `</body>`. It is included on all four existing templates:

- `templates/index.html`
- `templates/tumor_profile.html`
- `templates/gene_profile.html`
- `templates/tutorial.html`

### Template partial

To mirror the existing `templates/partials/nav.html` pattern, the footer
lives in a new partial: `templates/partials/footer.html`. Each of the four
pages includes it with `{% include 'partials/footer.html' %}`.

Footer markup:

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
        <a href="https://genie.synapse.org/" target="_blank" rel="noopener"
          >AACR Project GENIE</a
        >
        consortium.
      </p>
      <p class="mp-footer-links">
        <a href="https://genie.synapse.org/" target="_blank" rel="noopener"
          >Homepage</a
        >
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

### Logo asset

The logo URL provided by the user
(`https://genie.synapse.org/assets/GENIE-logo-D5F_ywVl.jpeg`) is a
hashed Synapse asset. Hashed filenames typically rotate on redeploy, so
hot-linking risks a broken image. The logo is downloaded once and
served locally from `static/genie-logo.jpeg`.

This is standard attribution practice: host the asset, link back to the
source.

### Styling

New CSS is added to `static/molpath.css` (which already owns shared
chrome like `.mp-nav`). Tokens from existing rules are reused where
possible.

Key rules:

- `.mp-footer` — full-width, top border, small vertical padding, muted
  background tint, sits below `<main>`.
- `.mp-footer-inner` — flex row, logo left, text block right, max-width
  matching the main layout, `gap` for spacing, horizontal padding.
- `.mp-footer-logo` — ~48px height, width auto, rendered crisply.
- `.mp-footer-text p` — tight line-height, small font-size (~0.82rem),
  muted color.
- `.mp-footer-links a` — existing link color, no underline by default,
  underline on hover.
- `.mp-footer-sep` — subtle separator dot.
- Responsive: below ~560px the flex row wraps to column; logo on top,
  text below, both left-aligned.

### Accessibility

- The logo `<img>` has a meaningful `alt` attribute
  (`"AACR Project GENIE"`).
- External links use `rel="noopener"` for security.
- Color contrast follows the existing body/link tokens (assumed
  WCAG-compliant already; no color changes).
- The footer is a semantic `<footer>` element.

## Files Changed

| File                                | Change                                        |
| ----------------------------------- | --------------------------------------------- |
| `templates/partials/footer.html`    | **New** — footer partial                      |
| `templates/index.html`              | Add `{% include 'partials/footer.html' %}`    |
| `templates/tumor_profile.html`      | Add `{% include 'partials/footer.html' %}`    |
| `templates/gene_profile.html`       | Add `{% include 'partials/footer.html' %}`    |
| `templates/tutorial.html`           | Add `{% include 'partials/footer.html' %}`    |
| `static/genie-logo.jpeg`            | **New** — downloaded logo asset               |
| `static/molpath.css`                | Add `.mp-footer*` rules + responsive wrap     |

## Verification

- Start the app locally and load `/`, `/tumor-profile`, `/gene-profile`,
  and `/tutorial`. Confirm footer renders on each page with logo, credit
  text, and both links.
- Click the logo, "Homepage", and "Manuscript" links and confirm each
  opens in a new tab with the expected destination.
- Resize the browser below ~560px and confirm the footer wraps cleanly
  without overflowing.
- Confirm the logo asset is served from `/static/genie-logo.jpeg` (not
  hot-linked from Synapse) by inspecting the network tab.

## Out of Scope / Future Work

- A proper "About" page describing the method, data version, and
  limitations (beyond the existing `/tutorial`).
- Displaying the specific GENIE release version used to build the
  model (e.g., "Built on GENIE v15.0-public").
