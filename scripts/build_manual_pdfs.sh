#!/usr/bin/env bash
#
# Prints the two manuals to PDF from the pages that serve them.
#
# There is deliberately no separate PDF source. The manual is a page of the site; this
# only asks a browser to print it, so the two can never drift apart. The print rules
# live at the foot of `static/css/restore.scss`.
#
# The pages are public, so no session is needed. Run it against a server that is
# already up:
#
#     python manage.py runserver 8000
#     scripts/build_manual_pdfs.sh
#
# Point it somewhere else by passing the base URL:
#
#     scripts/build_manual_pdfs.sh https://restore4life.icts-donana.es
#
# Re-run it after adding screenshots: the PDFs are built artefacts and are committed,
# because the site serves them from `static/` and the deploy does not run a browser.

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
OUTPUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/static/manual"

CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
if [[ -z "$CHROME" ]]; then
    echo "No Chrome or Chromium found; one of them is what does the printing." >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Chrome prints whatever it is given, including a connection-error page, and says
# nothing about it: a server that is down or in the middle of reloading yields a
# cheerful one-page PDF. Ask first.
if ! curl --silent --fail --retry 5 --retry-delay 2 --output /dev/null "${BASE_URL}/manual/"; then
    echo "No manual at ${BASE_URL}/manual/ -- is the server up?" >&2
    exit 1
fi

print_manual() {
    local path="$1" file="$2"
    echo "  ${BASE_URL}${path} → static/manual/${file}"
    # --virtual-time-budget waits for the fonts and images instead of printing a
    # half-loaded page; without it the first run comes out in a fallback typeface.
    "$CHROME" \
        --headless \
        --disable-gpu \
        --no-sandbox \
        --no-pdf-header-footer \
        --virtual-time-budget=15000 \
        --print-to-pdf="${OUTPUT_DIR}/${file}" \
        "${BASE_URL}${path}" 2>/dev/null
}

echo "Printing the manuals from ${BASE_URL}"
print_manual "/manual/earth-engine/" "restore4life-earth-engine.pdf"
print_manual "/manual/" "restore4life-user-manual.pdf"

echo
# How many pages a PDF has, by whatever means this machine offers. Only ever used to
# tell a manual from an error page, so an undercount does no harm: page objects inside
# compressed object streams are invisible to the fallback, and it still lands well
# above the threshold.
page_count() {
    if command -v pdfinfo >/dev/null; then
        pdfinfo "$1" 2>/dev/null | awk '/^Pages:/ {print $2}'
    else
        grep -ao '/Type[[:space:]]*/Pages\?' "$1" | grep -c '/Page$' || true
    fi
}

for file in restore4life-earth-engine.pdf restore4life-user-manual.pdf; do
    pages="$(page_count "${OUTPUT_DIR}/${file}")"
    if [[ "${pages:-0}" -lt 3 ]]; then
        echo "${file} came out with ${pages:-0} page(s): that is an error page, not a manual." >&2
        exit 1
    fi
    printf '  %-34s %2s pages  %s\n' "$file" "$pages" "$(du -h "${OUTPUT_DIR}/${file}" | cut -f1)"
done

echo
echo "Done. Both are linked from their own page once they exist." 
