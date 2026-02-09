# Utility Commands

Utilities provide file system access, spec downloading, and database diagnostics.

## File & TDoc Access

### `open`

Download (if needed), extract, and open a TDoc file with the system default application.

```bash
# Open a specific TDoc
tdoc-crawler open R1-2400001
```

### `checkout`

Download and extract TDoc(s) to the checkout folder (`~/.tdoc-crawler/checkout/`) for offline access.

```bash
# Batch checkout
tdoc-crawler checkout R1-2400001 S2-2400567
```

______________________________________________________________________

## Technical Specifications

### `open-spec` (alias: `os`)

Download and open the latest document for a specification.

```bash
# Open latest 23.501
tdoc-crawler open-spec 23.501

# Open release 17 version
tdoc-crawler open-spec 23.501 -r 17
```

### `checkout-spec` (alias: `cos`)

Batch download specification documents to the checkout folder.

**Features:**

- **Progress bar** for multi-spec operations.
- **Range syntax** support (e.g., `26130-26.140`).
- **Hierarchical organization** in the checkout folder.

```bash
# Checkout range of specs
tdoc-crawler checkout-spec 26130-26140
```

______________________________________________________________________

## Diagnostics

### `stats`

Display high-level database statistics.

```bash
# View database population status
tdoc-crawler stats
```
