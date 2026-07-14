# Deploy to Streamlit Community Cloud

This folder is ready to upload to a GitHub repository and deploy with `app.py` as the entrypoint.

## 1. Create the GitHub repository

Create a new GitHub repository, preferably private, and upload everything in this folder.

Do **not** create or commit `.streamlit/secrets.toml`. The included `.gitignore` already excludes it.

## 2. Create the Streamlit app

1. Sign in at Streamlit Community Cloud with GitHub.
2. Choose **Create app**.
3. Select the repository and branch.
4. Set the main file path to `app.py`.
5. Open **Advanced settings** and choose Python 3.12.
6. Paste the secrets shown below.
7. Deploy.

## 3. Configure secrets

In the Streamlit secrets box, enter:

```toml
OPENAI_API_KEY = "sk-your-key-here"
OPENAI_MODEL = "gpt-5.6"
```

For an extra in-app access-code screen, also add:

```toml
APP_PASSWORD = "your-household-access-code"
```

A private Streamlit app shared only with your household is preferable to relying only on the access code.

## 4. Share with your spouse

Use the app's sharing settings to invite your spouse's email address. Each person still installs the Chrome extension once on the computer they use for Walmart.

The extension can be downloaded directly from the app sidebar after deployment.

## 5. Make updates

Edit the files in GitHub or a GitHub Codespace and commit the changes. Streamlit Community Cloud detects repository updates and refreshes the deployed app automatically.

## Architecture note

The cloud app prepares and downloads `walmart_cart.json`. The locally installed Chrome extension imports that file and performs the Walmart search and cart steps in the user's existing signed-in browser session. Walmart credentials never go to Streamlit.
