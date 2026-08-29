# BorderGuard-AI — Live Demo & Presentation Script (5-Minute Walkthrough)

**Objective**: Demonstrate how BorderGuard-AI detects identity fraud, digital tampering, and unauthorized alterations across 6 problem statement modules.

---

## ⏱️ Minute-by-Minute Demo Flow

### [0:00 - 1:00] Ingestion & Genuine Baseline
1. Open the Next.js Officer Station Dashboard at `http://localhost:3000`.
2. Select the **"🟢 Genuine Passport"** preset (or drop a clean passport scan).
3. **Point out**:
   - **ICAO 9303 MRZ**: Checksum validation passed (100%).
   - **Validation Rules**: Expiry date > 6 months in future, valid format.
   - **ELA & Tampering**: Uniform compression across image, no Photoshop/GIMP EXIF tags.
   - **1:1 Face Match**: Facial embedding matches live checkpoint snapshot (>90% cosine similarity).
   - **Threat Score**: **14 / 100 (LOW)**.
   - Click **"APPROVE CLEARANCE"** $\rightarrow$ Immutably logged to hash-chain ledger.

---

### [1:00 - 2:15] Advanced Digital Forgery Detection (Photo-Swap & Text-Edit)
1. Click the **"🔴 Photo-Swap Tamper"** preset.
2. Switch to **Tab 3 ("FORGERY & ELA")**:
   - Show the interactive **Error Level Analysis (ELA) Heatmap**: The photo region lights up with extreme compression difference against the passport substrate.
   - Show **Photo Boundary Analysis**: Sharp Sobel variance indicates a spliced border.
3. Switch to **Tab 1 ("THREAT SUMMARY")**:
   - Risk score spikes to **84 / 100 (CRITICAL)**.
   - Show **AI Explainability Reasons Panel**: Directly points the officer to the exact forensic findings.
   - Click **"DENY ENTRY"**.

---

### [2:15 - 3:15] Watchlist & Multi-Identity Biometric Deduplication
1. Click the **"🚨 Watchlist / Blacklist"** preset.
   - Demonstrates instant cross-referencing against Interpol Red Notices $\rightarrow$ Risk score jumps to **95 / 100 (CRITICAL)**.
2. Switch to **Tab 4 ("1:1 BIOMETRICS")**:
   - Explain **1:N pgvector Deduplication Search**: Even if a traveler presents a fake passport with an altered name, their 512-d facial embedding clusters with their previous identity records.

---

### [3:15 - 4:30] The Cryptographic Audit Ledger & Live Tampering Catch (The Climax)
1. Switch to **Tab 5 ("AUDIT LEDGER")**:
   - Show the Merkle-style hash chain blocks.
   - Click **"Verify Chain Integrity"** $\rightarrow$ Animated report returns **"100% VALID — All Blocks Cryptographically Intact"**.
2. Click **"Simulate Attack"** (tampering with block #2 directly in database/memory).
3. Click **"Verify Chain Integrity"** again:
   - 🚨 **Immediate Security Alert**: **"TAMPERING DETECTED! HASH CHAIN BROKEN AT SEQUENCE #2"**.
   - Proves mathematically that insider threats cannot modify past scan records undetected.

---

### [4:30 - 5:00] Summary & Architecture Wrap-Up
- **Zero-Trust**: Edge processing + AES-256 encrypted storage + immutable hash chain.
- **Explainable**: Officer receives clear reasons, not opaque black-box numbers.
- **Multi-Modal**: OCR + ELA Forensics + Deep Biometrics + Real-time Rules.
