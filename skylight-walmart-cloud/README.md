# Skylight → Walmart Cart

A Streamlit Cloud–ready household tool that turns a Skylight grocery list into a reviewed Walmart cart workflow without Instacart.

## What is included

- Paste grocery lines or upload Skylight screenshots.
- Optional OpenAI image extraction using a key stored in Streamlit secrets.
- Review quantities, preferences, Walmart search terms, and package counts.
- Download a `walmart_cart.json` handoff file.
- Download the companion Manifest V3 Chrome extension directly from the app.
- Import the cart file into the extension and approve Walmart products before they are added.
- Final checkout, pickup selection, substitutions, and payment remain inside Walmart.

## Recommended deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the GitHub and Streamlit Community Cloud steps.

## Local development on macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For local screenshot extraction, either enter an OpenAI API key in the app or create `.streamlit/secrets.toml` from the example file. Never commit the real secrets file.

## Load the Chrome extension

1. Download it from the Streamlit app sidebar, or use the included `extension` folder.
2. Unzip the download.
3. Open `chrome://extensions`.
4. Enable **Developer mode**.
5. Choose **Load unpacked**.
6. Select the unzipped `skylight-walmart-extension` folder.

## Current limitations

- Walmart page changes may require updates to `extension/content.js`.
- Prices and pickup availability are read from the Walmart pages visible in the browser.
- Package-size optimization is still manual in this MVP.
- App data lives in the current Streamlit session and is not yet saved to a household database.
- The extension stops before checkout and never submits payment.
