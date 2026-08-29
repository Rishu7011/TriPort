# Threat Model & Security Architecture — BorderGuard-AI

## 1. System Overview & Scope
BorderGuard-AI operates in high-stakes border control environments where physical travel documents, live biometric streams, and officer decisions must be screened in real-time, protected against tampering, and cryptographically audited.

---

## 2. Trust Boundaries & Architecture

```
  ┌────────────────────────────────────────────────────────┐
  │ EDGE ENVIRONMENT (Checkpoint Lane / Terminal Scanner)  │
  │ • Passport Flatbed Optical Scanner                     │
  │ • Live Biometric Webcam / Anti-Spoof Camera           │
  │ • Local Edge Node / Officer Terminal                   │
  └──────────────────────────┬─────────────────────────────┘
                             │ TLS 1.3 / mTLS & Signed JWT
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ CENTRAL GATEWAY (BorderGuard Orchestrator)             │
  │ • RBAC Role Enforcement (Officer/Supervisor/Auditor)   │
  │ • Rate Limiting & Input Validation                     │
  │ • AES-256-GCM Sensitive Field Encryption               │
  └──────────┬───────────────────────────────┬─────────────┘
             │ Internal gRPC/REST            │
             ▼                               ▼
  ┌───────────────────────┐       ┌────────────────────────┐
  │ AI Forensic Services  │       │ Module 6 Audit Ledger  │
  │ (OCR, Tamper, Biometrics)     │ (Immutable Hash Chain) │
  └───────────────────────┘       └────────────────────────┘
```

---

## 3. Threat Vectors & Mitigations

### 3.1 Document Forgery & Digital Manipulation
- **Threat**: Bad actors modify passport numbers, expiry dates, or splice alternate facial portraits using image editing software (Photoshop, GIMP).
- **Mitigation**:
  - **Error Level Analysis (ELA)**: Re-compression analysis detects differing compression histories in modified text or photo boundaries.
  - **ICAO 9303 MRZ Checksums**: Mathematical check digits prevent undetectable text changes on genuine passports.
  - **Boundary Discontinuity Analysis**: OpenCV Sobel/variance analysis detects physical photo splice lines.
  - **Metadata Forensics**: EXIF parsing detects software signatures and inconsistent modification timestamps.

### 3.2 Biometric Spoofing & Identity Clustering
- **Threat**: Presentation attacks (printed photos, video playback on tablet, silicon masks) or using stolen documents across different checkpoints with different names.
- **Mitigation**:
  - **1:1 Face Verification**: 512-dimensional facial embeddings with cosine similarity scoring.
  - **1:N pgvector Deduplication**: Cross-document vector similarity search detects if the same biological individual has presented passports under multiple distinct identities.

### 3.3 Insider Threat & Audit Log Tampering
- **Threat**: A compromised border officer or database administrator attempts to retroactively alter scan records or erase an illicit entry clearance.
- **Mitigation**:
  - **Cryptographic Hash Chaining**: Every event payload is SHA-256 hashed and mathematically linked to the previous block's record hash:
    $$\text{record\_hash}_i = \text{SHA-256}(\text{payload\_hash}_i \parallel \text{record\_hash}_{i-1} \parallel \text{timestamp}_i)$$
  - **Zero-Mutation Guarantee**: Any alteration of past records breaks all downstream hashes and is immediately flagged by `verify_chain()`.

### 3.4 Data-at-Rest & In-Transit Interception
- **Threat**: Unauthorized database dump reveals traveller PII (names, document numbers, biometric vectors).
- **Mitigation**:
  - **Field-Level Encryption**: AES-256-GCM encryption for sensitive document fields and raw scans.
  - **PII Masking**: Partial string redaction for unauthorized viewports.

---

## 4. Known Hackathon Limitations & Production Roadmap
1. **Key Management**: Symmetric AES-256 keys are currently derived from environment variables. Production deployments should interface with AWS KMS or HashiCorp Vault.
2. **Hardware Security Modules (HSM)**: Production hash chains should sign each block header using an HSM-backed private key.
3. **Anti-Spoofing Depth**: Live webcam liveness leverages landmark motion/blink heuristics; hardware IR structured-light depth cameras are recommended for physical checkpoints.
