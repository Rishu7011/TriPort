/**
 * In-memory client cache for screening results.
 * Avoids the 5MB browser sessionStorage quota limit for high-res images,
 * enabling instantaneous 0ms page transitions without re-fetching from backend.
 */

const scanCache = new Map<string, any>();

export function setCachedScan(documentId: string, data: any): void {
  if (!documentId || !data) return;
  scanCache.set(documentId, data);

  if (typeof window !== "undefined" && window.sessionStorage) {
    try {
      // Store in sessionStorage with massive image strings omitted to protect quota
      const lightweight = {
        ...data,
        doc_image_url: data.doc_image_url?.startsWith("data:")
          ? undefined
          : data.doc_image_url,
      };
      sessionStorage.setItem(`triport_scan_${documentId}`, JSON.stringify(lightweight));
    } catch {
      // Ignore quota exceptions safely
    }
  }
}

export function getCachedScan(documentId: string): any | null {
  if (!documentId) return null;
  if (scanCache.has(documentId)) {
    return scanCache.get(documentId);
  }

  if (typeof window !== "undefined" && window.sessionStorage) {
    try {
      const item = sessionStorage.getItem(`triport_scan_${documentId}`);
      if (item) {
        const parsed = JSON.parse(item);
        scanCache.set(documentId, parsed);
        return parsed;
      }
    } catch {
      return null;
    }
  }
  return null;
}
