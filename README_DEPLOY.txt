RIFTBOUND MARKET PULSE — FREE DEPLOYMENT PACKAGE

FASTEST OPTION: CLOUDFLARE PAGES
1. Sign in to Cloudflare.
2. Go to Workers & Pages.
3. Create application -> Pages -> Direct Upload / Drag and drop.
4. Upload this ZIP or the unzipped folder.
5. Choose a project name such as riftbound-market-pulse.
6. Deploy.
7. Your site will be available at:
   https://YOUR-PROJECT.pages.dev

IMPORTANT
- index.html is the live dashboard.
- health.html tests whether the visitor's browser can reach the RiftHunt API.
- The dashboard waits at most 15 seconds for the API.
- Successful catalogue/price responses are cached in the browser and reused if a later refresh fails.
- No paid server is required. RiftHunt documents its API as keyless and browser-accessible with open CORS.

OPTIONAL LATER
For automatic deployments whenever code changes, place these files in a GitHub repository and connect that repository to Cloudflare Pages or GitHub Pages.
