# WhatTheSpec

[WhatTheSpec](https://whatthespec.net) is a **third-party convenience service**
for looking up metadata of a single TDoc — useful when you only know the TDoc
ID and the parent meeting is not available in your local database.

## ⚠️ Third-party service — no guarantees

WhatTheSpec is **not affiliated with 3GPP or ETSI** and is outside the control
of this project:

- There is no guarantee that the service or its API keeps working.
- API changes or downtime can break or degrade the affected `3gpp-crawler`
  features at any time, without notice.
- The official 3GPP sources always remain the source of truth.

## Role in 3gpp-crawler

The **regular workflow uses official 3GPP sources only**:

1. `crawl-meetings` — meeting metadata from official endpoints.
1. `tdoc crawl` — TDoc metadata from the meeting document lists (Excel sheets)
   published on the official 3GPP FTP server, meeting by meeting.
1. Single/missing TDocs are fetched from the official (unauthenticated) portal.

WhatTheSpec is involved only at the edges:

1. **Opt-in flag**: `--use-whatthespec` on `tdoc open` and `tdoc checkout`
   forces single-TDoc lookups through WhatTheSpec.
1. **Fallback**: when no EOL credentials are available, missing-TDoc fetches
   automatically fall back to WhatTheSpec. Orphan records (TDocs without a
   known parent meeting) are refreshed from WhatTheSpec, since it can resolve
   a single TDoc without meeting context.

For specifications, the official 3GPP source is tried first; WhatTheSpec
serves as a fallback.
