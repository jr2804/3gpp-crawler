# WhatTheSpec

WhatTheSpec ([whatthespec.net](https://whatthespec.net)) is the **primary data source** for metadata indexing in `3gpp-crawler`. It is a community-maintained service that catalogs 3GPP technical documents.

## Why it's useful

1. **Primary Source**: It provides fast, unauthenticated access to TDoc information without requiring ETSI credentials.
1. **Efficiency**: Simple metadata queries are optimized for performance compared to scraping official portals.
1. **Open Access**: Accessible to anyone without an EOL account.

## Use in 3GPP Crawler

`3gpp-crawler` leverages WhatTheSpec as its first line of data retrieval:

1. **Default Discovery**: In `open` and `checkout` commands, the tool first attempts to resolve TDoc metadata via WhatTheSpec.
1. **Metadata Source**: In `crawl-specs`, WhatTheSpec is the primary source for technical specification metadata.

## ⚠️ The Fallback Strategy

Because WhatTheSpec is a community-maintained service and not officially affiliated with 3GPP, `3gpp-crawler` implements a **3GPP-official fallback** using EOL credentials.

If WhatTheSpec is unavailable or fail to provide the required data, the tool can fall back to the [official 3GPP portal](misc.md#etsi-online-eol-credentials) (requires authentication). This ensures the tool remains resilient and always has a path to the official source of truth.
