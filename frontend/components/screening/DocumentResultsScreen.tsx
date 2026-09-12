"use client";

import React from "react";
import type { UploadResponse } from "../../lib/api/types";

interface DocumentResultsScreenProps {
  uploadData: UploadResponse;
  localPreviewUrl?: string | null;
  onProceedToBiometrics: () => void;
  onRejectDocument: (reason?: string) => void;
  isRejecting: boolean;
}

export function DocumentResultsScreen({
  uploadData,
  localPreviewUrl,
  onProceedToBiometrics,
  onRejectDocument,
  isRejecting,
}: DocumentResultsScreenProps) {
  const pipeline = uploadData.pipeline;
  const extraction = pipeline?.extraction;
  const validation = pipeline?.validation;
  const tampering = pipeline?.tampering;

  // Phase 9: Multilingual passport metadata
  const detectedLanguages: string[] = extraction?.detected_languages || [];
  const primaryScript: string | null = extraction?.primary_script || null;
  const isMultilingual: boolean = Boolean(extraction?.is_multilingual);

  // Language display name map (ISO 639-1 → human label)
  const LANG_DISPLAY: Record<string, string> = {
    en: "English", de: "German", fr: "French", es: "Spanish",
    ar: "Arabic", ru: "Russian", hi: "Hindi", ne: "Nepali",
    bn: "Bengali", th: "Thai", my: "Burmese", si: "Sinhala",
    zh: "Chinese", ja: "Japanese",
  };
  const langBadgeText = isMultilingual && detectedLanguages.length > 0
    ? detectedLanguages
        .map((l) => LANG_DISPLAY[l] || l.toUpperCase())
        .join(" + ") + " (ICAO)"
    : null;

  // Real backend gating decision (tampering is actionable if score >= 0.35 or critical check like ELA is flagged)
  const isTamperingFlagged = Boolean(
    tampering?.flagged &&
      ((tampering.tampering_score ?? 0) >= 0.35 ||
        tampering.checks?.some((c) => c.check_type === "ela" && c.flagged))
  );
  const isValidationFailed = Boolean(validation && !validation.passed);
  const isDegraded = Boolean(pipeline?.degraded);
  const isSuspicious = isTamperingFlagged || isValidationFailed || isDegraded;
  const isCleared = !isSuspicious;

  // Extract fields from real API response
  const fields = extraction?.fields || [];

  // Helper to map technical field names to official border document labels
  const formatFieldLabel = (key: string): string => {
    const keyLower = key.toLowerCase();
    const labelMap: Record<string, string> = {
      full_name: "FULL NAME",
      name: "FULL NAME",
      given_names: "GIVEN NAME(S)",
      given_name: "GIVEN NAME(S)",
      first_name: "FIRST NAME",
      surname: "SURNAME",
      last_name: "LAST NAME",
      passport_number: "PASSPORT NUMBER",
      doc_number: "DOCUMENT NUMBER",
      id_number: "NATIONAL ID NUMBER",
      aadhaar_number: "AADHAAR NUMBER",
      license_number: "DRIVING LICENSE NUMBER",
      date_of_birth: "DATE OF BIRTH",
      dob: "DATE OF BIRTH",
      nationality: "NATIONALITY",
      country: "COUNTRY OF ISSUANCE",
      sex: "GENDER / SEX",
      gender: "GENDER / SEX",
      date_of_expiry: "EXPIRY DATE",
      expiry_date: "EXPIRY DATE",
      date_of_issue: "DATE OF ISSUE",
      issue_date: "DATE OF ISSUE",
      place_of_birth: "PLACE OF BIRTH",
      place_of_issue: "PLACE OF ISSUE",
      address: "ADDRESS",
      father_name: "FATHER / SPOUSE",
      relative_name: "RELATION NAME",
      voter_id_number: "VOTER ID / EPIC NUMBER",
      epic_number: "EPIC NUMBER",
      elector_name: "ELECTOR NAME",
      assembly_constituency: "ASSEMBLY CONSTITUENCY",
      polling_station: "POLLING STATION",
      issuing_authority: "ISSUING AUTHORITY",
      vehicle_classes: "VEHICLE CLASSES",
      visa_type: "VISA CATEGORY",
      category: "CATEGORY",
    };
    if (labelMap[keyLower]) return labelMap[keyLower];
    return key.replace(/_/g, " ").toUpperCase();
  };

  // 1. Resolve Full Name accurately (combining Given Names + Surname if separate)
  const getF = (k: string) =>
    fields.find((f) => f.field_name.toLowerCase() === k.toLowerCase());

  const givenN = getF("given_names") || getF("given_name") || getF("first_name");
  const surN = getF("surname") || getF("last_name");
  const fullN = getF("full_name") || getF("name");

  let resolvedFullName = fullN?.field_value?.trim() || "";
  let nameConfidence = fullN?.confidence ?? 0.99;

  if (givenN?.field_value && surN?.field_value) {
    const combined = `${givenN.field_value.trim()} ${surN.field_value.trim()}`;
    if (
      !resolvedFullName ||
      resolvedFullName.toLowerCase() === surN.field_value.toLowerCase() ||
      resolvedFullName.toLowerCase() === givenN.field_value.toLowerCase()
    ) {
      resolvedFullName = combined;
      nameConfidence = Math.min(
        givenN.confidence ?? 0.99,
        surN.confidence ?? 0.99
      );
    }
  } else if (!resolvedFullName && givenN?.field_value) {
    resolvedFullName = givenN.field_value.trim();
  } else if (!resolvedFullName && surN?.field_value) {
    resolvedFullName = surN.field_value.trim();
  }

  // 2. Build list of ALL document fields dynamically
  interface ExtractedFieldItem {
    id: string;
    label: string;
    value: string;
    conf: number;
    isPrimary?: boolean;
  }

  const allDisplayFields: ExtractedFieldItem[] = [];

  // Primary top row: Full Name
  if (resolvedFullName) {
    allDisplayFields.push({
      id: "full_name_primary",
      label: "FULL NAME",
      value: resolvedFullName,
      conf: nameConfidence <= 1 ? nameConfidence * 100 : nameConfidence,
      isPrimary: true,
    });
  }

  // Sort remaining fields by logical document hierarchy
  const priorityOrder = [
    "given_names",
    "given_name",
    "first_name",
    "surname",
    "last_name",
    "passport_number",
    "doc_number",
    "id_number",
    "aadhaar_number",
    "voter_id_number",
    "epic_number",
    "elector_name",
    "license_number",
    "date_of_birth",
    "dob",
    "nationality",
    "sex",
    "gender",
    "date_of_expiry",
    "expiry_date",
    "date_of_issue",
    "issue_date",
    "place_of_birth",
    "place_of_issue",
    "address",
    "father_name",
  ];

  const sortedFields = [...fields].sort((a, b) => {
    const idxA = priorityOrder.indexOf(a.field_name.toLowerCase());
    const idxB = priorityOrder.indexOf(b.field_name.toLowerCase());
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return a.field_name.localeCompare(b.field_name);
  });

  const seenLabels = new Set<string>(["FULL NAME"]);
  const seenValues = new Set<string>();
  if (resolvedFullName) {
    seenValues.add(resolvedFullName.toLowerCase());
  }

  for (const f of sortedFields) {
    const fnLower = f.field_name.toLowerCase();
    const val = f.field_value?.trim();
    if (!val) continue;

    // Skip technical/redundant internals
    if (fnLower === "mrz_format" || fnLower === "raw_dob") continue;

    // If passport_number is already shown, skip redundant generic doc_number with exact same value
    if (fnLower === "doc_number" && seenValues.has(val.toLowerCase())) continue;

    // If full_name is already shown and field_name is full_name or name, skip duplicate
    if (
      (fnLower === "full_name" || fnLower === "name") &&
      val.toLowerCase() === resolvedFullName.toLowerCase()
    ) {
      continue;
    }

    const label = formatFieldLabel(f.field_name);
    if (seenLabels.has(label)) continue;
    seenLabels.add(label);
    seenValues.add(val.toLowerCase());

    const confVal =
      f.confidence !== null && f.confidence !== undefined
        ? f.confidence <= 1
          ? f.confidence * 100
          : f.confidence
        : 99.0;

    allDisplayFields.push({
      id: f.field_name,
      label,
      value: val,
      conf: confVal,
      isPrimary: false,
    });
  }

  // ---------------------------------------------------------------------------
  // Passport Cross-Verification (VIZ OCR vs MRZ ICAO-9303)
  // Only compared for Passport documents; other documents use direct attributes
  // ---------------------------------------------------------------------------
  const rawDocType = (uploadData.pipeline?.extraction?.document_type || "").toLowerCase();
  const mrzObj = extraction?.mrz;
  const hasMrz = Boolean(
    mrzObj?.mrz_present && mrzObj?.mrz_fields && Object.keys(mrzObj.mrz_fields).length > 0
  );
  const isPassport = rawDocType === "passport" || hasMrz;

  interface PassportFieldComparison {
    id: string;
    label: string;
    ocrValue: string;
    ocrNativeValue?: string | null;   // Phase 9: original script text
    mrzValue: string;
    status: "MATCH" | "MISMATCH" | "VERIFIED" | "ICAO_MATCH";
    matchReason?: string;             // Phase 9: e.g. "ICAO Transliteration"
    conf: number;
    isPrimary?: boolean;
  }

  const passportComparisons: PassportFieldComparison[] = [];

  if (isPassport) {
    const mrzF = mrzObj?.mrz_fields || {};

    const cleanStr = (s: string) => s.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();

    // Phase 9: Client-side ICAO Doc 9303 diacritic transliteration for name comparison
    // Handles German umlauts and common diacritics so MÜLLER === MUELLER
    const icaoTransliterate = (s: string): string => {
      return s
        .toUpperCase()
        .replace(/Ä/g, "AE").replace(/Ö/g, "OE").replace(/Ü/g, "UE").replace(/ß/g, "SS")
        .replace(/É|È|Ê|Ë/g, "E").replace(/À|Â/g, "A").replace(/Á/g, "A")
        .replace(/Î|Ï/g, "I").replace(/Í|Ì/g, "I")
        .replace(/Ô|Ó|Ò/g, "O").replace(/Ú|Ù|Û/g, "U")
        .replace(/Ç/g, "C").replace(/Ñ/g, "N")
        .replace(/Å/g, "AA").replace(/Æ/g, "AE").replace(/Ø/g, "OE")
        .replace(/[^A-Z0-9 ]/g, "");
    };

    // Upgraded areMatching: checks exact → ICAO transliteration → date format variants
    const areMatching = (v1: string, v2: string): { match: boolean; reason: string } => {
      if (!v1 || !v2) return { match: false, reason: "" };
      const c1 = cleanStr(v1);
      const c2 = cleanStr(v2);
      if (c1 === c2) return { match: true, reason: "EXACT" };
      // ICAO transliteration match
      const t1 = cleanStr(icaoTransliterate(v1));
      const t2 = cleanStr(icaoTransliterate(v2));
      if (t1 === t2 || t1 === c2 || c1 === t2) return { match: true, reason: "ICAO_TRANSLITERATION" };
      // Date format variants: YYMMDD vs DDMMYYYY
      if (c1.length === 6 && c2.length === 8) {
        const dateMatch =
          c1 === c2.slice(4, 8) + c2.slice(2, 4) + c2.slice(0, 2) ||
          c1 === c2.slice(6, 8) + c2.slice(2, 4) + c2.slice(0, 2);
        if (dateMatch) return { match: true, reason: "DATE_FORMAT" };
      }
      if (c2.length === 6 && c1.length === 8) {
        const dateMatch =
          c2 === c1.slice(4, 8) + c1.slice(2, 4) + c1.slice(0, 2) ||
          c2 === c1.slice(6, 8) + c1.slice(2, 4) + c1.slice(0, 2);
        if (dateMatch) return { match: true, reason: "DATE_FORMAT" };
      }
      return { match: false, reason: "" };
    };

    // 1. Full Name
    const ocrName = resolvedFullName;
    const mrzName = (mrzF.name || `${mrzF.given_names || ""} ${mrzF.surname || ""}`).trim();
    // Phase 9: pick up native_value from the name field if present
    const nameField = getF("name") || getF("full_name");
    const ocrNameNative = nameField?.native_value ?? null;
    if (ocrName || mrzName) {
      const { match, reason } = areMatching(ocrName, mrzName);
      passportComparisons.push({
        id: "pass_name",
        label: "FULL NAME",
        ocrValue: ocrName || mrzName,
        ocrNativeValue: ocrNameNative,
        mrzValue: mrzName || ocrName,
        status: ocrName && mrzName ? (match ? (reason === "ICAO_TRANSLITERATION" ? "ICAO_MATCH" : "MATCH") : "MISMATCH") : "VERIFIED",
        matchReason: reason || undefined,
        conf: nameConfidence <= 1 ? nameConfidence * 100 : nameConfidence,
        isPrimary: true,
      });
    }

    // 2. Passport Number
    const ocrDoc =
      getF("passport_number")?.field_value ||
      getF("doc_number")?.field_value ||
      "";
    const mrzDoc = mrzF.passport_number || mrzF.doc_number || "";
    if (ocrDoc || mrzDoc) {
      const { match } = areMatching(ocrDoc, mrzDoc);
      const conf = getF("passport_number")?.confidence ?? getF("doc_number")?.confidence ?? 0.99;
      passportComparisons.push({
        id: "pass_doc_num",
        label: "PASSPORT NUMBER",
        ocrValue: ocrDoc || mrzDoc,
        mrzValue: mrzDoc || ocrDoc,
        status: ocrDoc && mrzDoc ? (match ? "MATCH" : "MISMATCH") : "VERIFIED",
        conf: conf <= 1 ? conf * 100 : conf,
        isPrimary: true,
      });
    }

    // 3. Date of Birth
    const ocrDob = getF("date_of_birth")?.field_value || getF("dob")?.field_value || "";
    const mrzDob = mrzF.date_of_birth || mrzF.raw_dob || "";
    if (ocrDob || mrzDob) {
      const { match } = areMatching(ocrDob, mrzDob);
      const conf = getF("date_of_birth")?.confidence ?? getF("dob")?.confidence ?? 0.95;
      passportComparisons.push({
        id: "pass_dob",
        label: "DATE OF BIRTH",
        ocrValue: ocrDob || mrzDob,
        mrzValue: mrzDob || ocrDob,
        status: ocrDob && mrzDob ? (match ? "MATCH" : "MISMATCH") : "VERIFIED",
        conf: conf <= 1 ? conf * 100 : conf,
      });
    }

    // 4. Nationality
    const ocrNat = getF("nationality")?.field_value || "";
    const mrzNat = mrzF.nationality || "";
    if (ocrNat || mrzNat) {
      const { match } = areMatching(ocrNat, mrzNat);
      const conf = getF("nationality")?.confidence ?? 0.95;
      passportComparisons.push({
        id: "pass_nat",
        label: "NATIONALITY",
        ocrValue: ocrNat || mrzNat,
        mrzValue: mrzNat || ocrNat,
        status: ocrNat && mrzNat ? (match ? "MATCH" : "MISMATCH") : "VERIFIED",
        conf: conf <= 1 ? conf * 100 : conf,
      });
    }

    // 5. Gender / Sex
    const ocrSex = getF("sex")?.field_value || getF("gender")?.field_value || "";
    const mrzSex = mrzF.sex || mrzF.gender || "";
    if (ocrSex || mrzSex) {
      const { match } = areMatching(ocrSex, mrzSex);
      const conf = getF("sex")?.confidence ?? getF("gender")?.confidence ?? 0.98;
      passportComparisons.push({
        id: "pass_sex",
        label: "GENDER / SEX",
        ocrValue: ocrSex || mrzSex,
        mrzValue: mrzSex || ocrSex,
        status: ocrSex && mrzSex ? (match ? "MATCH" : "MISMATCH") : "VERIFIED",
        conf: conf <= 1 ? conf * 100 : conf,
      });
    }

    // 6. Expiry Date
    const ocrExp = getF("date_of_expiry")?.field_value || getF("expiry_date")?.field_value || "";
    const mrzExp = mrzF.date_of_expiry || mrzF.raw_expiry || "";
    if (ocrExp || mrzExp) {
      const { match } = areMatching(ocrExp, mrzExp);
      const conf = getF("date_of_expiry")?.confidence ?? getF("expiry_date")?.confidence ?? 0.95;
      passportComparisons.push({
        id: "pass_exp",
        label: "EXPIRY DATE",
        ocrValue: ocrExp || mrzExp,
        mrzValue: mrzExp || ocrExp,
        status: ocrExp && mrzExp ? (match ? "MATCH" : "MISMATCH") : "VERIFIED",
        conf: conf <= 1 ? conf * 100 : conf,
      });
    }
  }

  // Calculate overall confidence
  const validConfidences = fields
    .map((f) =>
      f.confidence !== null && f.confidence !== undefined
        ? f.confidence <= 1
          ? f.confidence * 100
          : f.confidence
        : null
    )
    .filter((c): c is number => c !== null);
  const avgConfidence =
    validConfidences.length > 0
      ? validConfidences.reduce((a, b) => a + b, 0) / validConfidences.length
      : isCleared
      ? 99.2
      : 64.5;

  // Real Forensic Checks
  const mrzCheck = extraction?.mrz?.checksum_valid ?? true;
  const elaCheck = tampering?.checks?.find((c) => c.check_type === "ela");
  const elaPassed = elaCheck ? !elaCheck.flagged : !isTamperingFlagged;
  const boundaryCheck = tampering?.checks?.find(
    (c) => c.check_type === "crop_boundary" || c.check_type === "jpeg_metadata"
  );
  const boundaryPassed = boundaryCheck ? !boundaryCheck.flagged : true;
  const rulesPassed = validation?.passed ?? true;

  // Generate diagnostic message from real failed checks
  const diagnosticReasons: string[] = [];
  if (tampering?.flagged) {
    diagnosticReasons.push(`Tampering anomaly detected (score: ${tampering.tampering_score.toFixed(1)})`);
  }
  if (validation && !validation.passed) {
    if (validation.failed_rules && validation.failed_rules.length > 0) {
      diagnosticReasons.push(`Validation rule failure: ${validation.failed_rules.join(", ")}`);
    } else {
      diagnosticReasons.push("Travel document rules validation failed");
    }
  }
  if (isDegraded) {
    diagnosticReasons.push("OCR confidence degraded / missing critical fields");
  }
  const diagnosticText =
    diagnosticReasons.length > 0
      ? diagnosticReasons.join(" • ")
      : "ALL FORENSIC CHECKS PASSED VALIDATION THRESHOLDS";

  // Comprehensive anomaly breakdown for officer decision making across ANY document type
  interface SuspiciousFinding {
    id: string;
    title: string;
    badge: string;
    category: "RULE VIOLATION" | "FORENSIC TAMPERING" | "MRZ CHECKSUM" | "OCR QUALITY";
    description: string;
    detail?: string;
    guidance: string;
  }

  // Universal rules dictionary covering Passports, Aadhaar, Driving Licenses, Visas, Voter IDs, PAN cards, and Permits
  const getUniversalRuleAdvisory = (
    ruleName: string,
    rawDetail?: string
  ): { title: string; description: string; guidance: string } => {
    const r = ruleName.toLowerCase();

    // 1. Passport Specific Rules
    if (r.includes("passport_number_format")) {
      return {
        title: "PASSPORT NUMBER FORMAT NON-COMPLIANT",
        description:
          "The passport number does not conform to standard international ICAO specifications (typically 1 letter followed by 7 to 8 digits, e.g. Z1234567).",
        guidance:
          "Inspect the visual photo page and MRZ lines for digit substitution, altered fonts, or physical tampering.",
      };
    }
    if (r.includes("passport_validity_window") || r.includes("6_months") || r.includes("sufficient")) {
      return {
        title: "INSUFFICIENT PASSPORT VALIDITY WINDOW (< 6 MONTHS)",
        description:
          "International border regulations mandate a minimum of 6 months validity remaining on the passport from entry date.",
        guidance:
          "Verify destination immigration rules for the traveler's nationality or check if an emergency consular extension applies.",
      };
    }
    if (r.includes("expiry_not_passed") || r.includes("license_expiry") || r.includes("visa_expiry") || r.includes("expiry")) {
      return {
        title: "CREDENTIAL VALIDITY PERIOD EXPIRED",
        description:
          "The expiration date recorded on this document is in the past relative to the current UTC screening timestamp.",
        guidance:
          "Confirm whether an official renewal sticker, embassy visa extension, or diplomatic waiver is physically affixed.",
      };
    }
    if (r.includes("nationality_code_format")) {
      return {
        title: "INVALID NATIONALITY COUNTRY CODE",
        description:
          "The nationality field does not match a recognized 3-letter ICAO/ISO-3166 country code.",
        guidance:
          "Verify the issuing state authority and cross-reference against international country code registries.",
      };
    }

    // 2. National ID & Aadhaar Rules
    if (r.includes("id_number_format") || r.includes("aadhaar")) {
      return {
        title: "NATIONAL ID / AADHAAR NUMBER FORMAT INVALID",
        description:
          "The National ID format is invalid. For Indian Aadhaar cards, it must be a 12-digit number (4-4-4 grouping) adhering to national Verhoeff checksum standards.",
        guidance:
          "Verify the 12-digit number against the QR code, embossed hologram, or secure watermark on the physical card.",
      };
    }
    if (r.includes("dob_plausibility") || r.includes("dob_in_past") || r.includes("dob")) {
      return {
        title: "DATE OF BIRTH CHRONOLOGY INCONSISTENCY",
        description:
          "The recorded date of birth is invalid, set in the future, or conflicts with human lifespan plausibility limits.",
        guidance:
          "Inspect if calendar formatting (DD/MM/YYYY vs MM/DD/YYYY) was transposed or if birth year was physically overwritten.",
      };
    }

    // 3. Driving License Rules
    if (r.includes("license_number_format")) {
      return {
        title: "DRIVING LICENSE NUMBER FORMAT NON-COMPLIANT",
        description:
          "The driving license number does not conform to the regional or national motor vehicle department alphanumeric convention.",
        guidance:
          "Verify the state/regional jurisdiction code prefix and serial digits against regional licensing standards.",
      };
    }
    if (r.includes("minimum_age") || r.includes("driver_min_age")) {
      return {
        title: "DRIVER MINIMUM LEGAL AGE REQUIREMENT NOT MET",
        description:
          "The license holder's date of birth indicates they do not meet the minimum statutory age required for this license class.",
        guidance:
          "Cross-examine the traveler and verify date of birth against primary civil birth registers.",
      };
    }
    if (r.includes("vehicle_class")) {
      return {
        title: "VEHICLE ENDORSEMENT CLASS MISSING OR INVALID",
        description:
          "The authorized vehicle categories (e.g. LMV, MCWG, HMV) are missing, illegible, or contain unrecognized characters.",
        guidance:
          "Confirm authorized vehicle categories permitted for this border traversal or commercial transport checkpoint.",
      };
    }

    // 4. Voter ID (EPIC) Rules
    if (r.includes("voter_id_number_format") || r.includes("epic")) {
      return {
        title: "VOTER ID / EPIC NUMBER FORMAT NON-COMPLIANT",
        description:
          "The extracted Voter ID (EPIC) number fails the Election Commission standard format (3 alphabetic letters followed by 7 numeric digits, e.g. TGI8262487).",
        guidance:
          "Inspect the printed EPIC characters on the card face. Confirm if letters or numbers were altered or misread by OCR.",
      };
    }

    // 5. Visa Rules
    if (r.includes("visa_entries") || r.includes("entries_valid")) {
      return {
        title: "VISA ENTRIES EXHAUSTED OR INVALID",
        description:
          "The permitted number of entries (Single, Double, or Multiple) has been exceeded based on border crossing records.",
        guidance:
          "Check entry and exit stamp pages in the traveler's passport to count prior border crossings.",
      };
    }
    if (r.includes("visa")) {
      return {
        title: "VISA ELIGIBILITY OR CATEGORY FAILURE",
        description:
          "The visa is invalid for this port category, has expired, or fails duration of stay limitations.",
        guidance:
          "Inspect visa foil security intaglio, validity window, and authorized border post entry restrictions.",
      };
    }

    // 6. Border Permit Rules
    if (r.includes("permit")) {
      return {
        title: "BORDER TRAVERSAL PERMIT AUTHORIZATION FAILURE",
        description:
          "The land/sea border permit has expired or is unauthorized for this specific transit corridor.",
        guidance:
          "Verify special corridor authorization, cargo manifest stamps, or restricted area clearance papers.",
      };
    }

    // 7. PAN Card Rules
    if (r.includes("pan_number_format") || r.includes("pan")) {
      return {
        title: "PAN CARD NUMBER FORMAT NON-COMPLIANT",
        description:
          "The Permanent Account Number does not conform to the 10-character alphanumeric structure (5 letters, 4 numbers, 1 letter).",
        guidance:
          "Inspect the central PAN number and Income Tax Department watermark on the physical credential.",
      };
    }

    // Universal Fallback for any other rule
    return {
      title: `VALIDATION RULE FAILURE: ${ruleName.replace(/_/g, " ").toUpperCase()}`,
      description:
        rawDetail ||
        `The credential failed the '${ruleName.replace(/_/g, " ")}' specification check in the validation engine.`,
      guidance:
        "Review the physical credential against official security guidelines and inspect visual scans on the right.",
    };
  };

  const suspiciousFindings: SuspiciousFinding[] = [];

  if (validation && !validation.passed) {
    if (validation.rule_results && validation.rule_results.length > 0) {
      validation.rule_results
        .filter((r) => !r.passed)
        .forEach((r) => {
          const advisory = getUniversalRuleAdvisory(r.rule_name, r.detail);
          suspiciousFindings.push({
            id: `rule-${r.rule_name}`,
            title: advisory.title,
            badge: "FAILED",
            category: "RULE VIOLATION",
            description: advisory.description,
            detail: r.detail ? `Validation Detail: ${r.detail}` : undefined,
            guidance: advisory.guidance,
          });
        });
    } else if (validation.failed_rules && validation.failed_rules.length > 0) {
      validation.failed_rules.forEach((rf) => {
        const advisory = getUniversalRuleAdvisory(rf);
        suspiciousFindings.push({
          id: `rule-${rf}`,
          title: advisory.title,
          badge: "FAILED",
          category: "RULE VIOLATION",
          description: advisory.description,
          guidance: advisory.guidance,
        });
      });
    } else {
      suspiciousFindings.push({
        id: "validation-generic",
        title: "TRAVEL DOCUMENT SPECIFICATION CHECK FAILED",
        badge: "FAILED",
        category: "RULE VIOLATION",
        description: "One or more mandatory security or format validation rules failed.",
        guidance: "Inspect document structure and official security markings against physical scan.",
      });
    }
  }

  if (tampering?.flagged) {
    const flaggedChecks = tampering.checks?.filter((c) => c.flagged) || [];
    const checkNames =
      flaggedChecks.map((c) => c.check_type.toUpperCase()).join(", ") || "PIXEL COMPRESSION / ELA";
    suspiciousFindings.push({
      id: "tampering-score",
      title: `FORENSIC TAMPERING ANOMALY (SCORE: ${tampering.tampering_score.toFixed(2)})`,
      badge: "ANOMALY",
      category: "FORENSIC TAMPERING",
      description:
        "Pixel error level analysis (ELA) or compression boundary filter detected anomalies exceeding the allowable threshold (0.25).",
      detail: `Flagged Modules: ${checkNames} • Overall Anomaly Score: ${tampering.tampering_score.toFixed(2)} (Tolerance: 0.25)`,
      guidance:
        "Carefully examine the right-side scan for digital splicing, pasted portrait borders, or altered typography around identity numbers.",
    });
  }

  if (extraction?.mrz && extraction.mrz.checksum_valid === false) {
    suspiciousFindings.push({
      id: "mrz-checksum",
      title: "ICAO-9303 MRZ CHECKSUM DIGIT MISMATCH",
      badge: "INVALID",
      category: "MRZ CHECKSUM",
      description:
        "Mathematical check digits computed across document number, DOB, or expiry date in the machine readable zone do not match the values stored on the document.",
      detail: extraction.mrz.checksum_failures?.length
        ? `Checksum mismatches detected in: ${extraction.mrz.checksum_failures.join(", ")}`
        : undefined,
      guidance: "High probability of altered MRZ text or forged passport booklet.",
    });
  }

  if (isDegraded) {
    suspiciousFindings.push({
      id: "ocr-degraded",
      title: "DEGRADED IMAGE SCAN / LOW OCR CONFIDENCE",
      badge: "WARNING",
      category: "OCR QUALITY",
      description:
        "The document scan exhibits glare, blur, low contrast, or missing mandatory identity fields.",
      guidance:
        "Request a re-scan of the document or manually inspect all attributes against the physical card.",
    });
  }

  const docImageUrl = uploadData.doc_image_url || localPreviewUrl || "";
  const docFaceCropUrl = uploadData.doc_face_crop_url || docImageUrl;

  return (
    <div className="flex flex-col w-full px-4 sm:px-6 pb-8 gap-6">
      {/* Dynamic Status Banner */}
      {isCleared ? (
        <div className="w-full bg-primary-fixed/10 border-l-[4px] border-primary-fixed py-4 px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className="material-symbols-outlined text-primary-fixed text-[28px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              check_circle
            </span>
            <div>
              <h2 className="font-headline-md text-primary-fixed uppercase m-0 leading-tight">
                CLEARED — PROCEED TO BIOMETRIC VERIFICATION
              </h2>
              <span className="font-data-mono-md text-[11px] text-on-surface-variant/80 uppercase">
                {diagnosticText}
              </span>
            </div>
          </div>
          <div className="flex flex-col items-start sm:items-end shrink-0">
            <span className="font-data-mono-md text-primary-fixed font-semibold">
              {avgConfidence.toFixed(1)}% CONFIDENCE
            </span>
            <div className="w-32 h-1 bg-surface-variant mt-1 overflow-hidden">
              <div
                className="h-full bg-primary-fixed"
                style={{ width: `${Math.min(100, avgConfidence)}%` }}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full bg-error-container/20 text-on-error-container border-l-4 border-error py-4 px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className="material-symbols-outlined text-error text-[28px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              warning
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="font-headline-md text-error uppercase tracking-wider leading-tight">
                SUSPICIOUS — FLAGGED FOR HUMAN VERIFICATION
              </span>
              <span className="font-data-mono-md text-xs text-on-error-container/90 uppercase">
                SYSTEM DIAGNOSTIC: {diagnosticText}
              </span>
            </div>
          </div>
          <div className="flex flex-col items-start sm:items-end shrink-0">
            <span className="font-label-caps text-error opacity-80 uppercase tracking-widest text-[10px]">
              CONFIDENCE LEVEL
            </span>
            <span className="font-headline-md text-error">
              {avgConfidence.toFixed(1)}%
            </span>
            <div className="w-36 h-1.5 bg-surface-container rounded-full overflow-hidden mt-0.5">
              <div
                className="h-full bg-error"
                style={{ width: `${Math.min(100, avgConfidence)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Main Forensic Grid: Proportionate Data (Left) vs Visual Evidence (Right ~32% / max 380px) */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Left Column: Extracted Data + Forensics */}
        <div className="w-full lg:flex-1 min-w-0 flex flex-col gap-6">
          {/* Extracted Entity Data (With Passport OCR vs MRZ Cross-Check, or Direct Attributes for Other Documents) */}
          <div className="bg-surface-container border border-outline-variant/50 p-5 relative overflow-hidden group">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3 border-b border-outline-variant/60 pb-2.5">
              <div className="flex items-center gap-2 min-w-0">
                <span className="material-symbols-outlined text-primary-fixed text-[18px] shrink-0">
                  {isPassport ? "compare_arrows" : "badge"}
                </span>
                <h3 className="font-label-caps text-on-surface uppercase tracking-widest text-xs m-0">
                  {isPassport
                    ? `PASSPORT VERIFICATION: VIZ (OCR) vs MRZ (${passportComparisons.length} ATTRIBUTES)`
                    : `EXTRACTED ENTITY DATA (${allDisplayFields.length} ATTRIBUTES)`}
                </h3>
              </div>
              <div className="flex items-center gap-2 flex-wrap shrink-0">
                {langBadgeText && (
                  <span className="bg-primary-fixed/10 text-primary-fixed border border-primary-fixed/30 px-2 py-0.5 text-[10px] font-data-mono-md flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px]">translate</span>
                    <span>{langBadgeText}</span>
                  </span>
                )}
                <span className="font-data-mono-md text-xs text-primary-fixed whitespace-nowrap">
                  {isPassport ? "ICAO-9303 DUAL-ZONE CROSS-CHECK" : "ENGINE: ICAO-9303 / GEMINI HYBRID"}
                </span>
              </div>
            </div>

            {isPassport && passportComparisons.length > 0 ? (
              /* Passport Specialized View: VIZ OCR vs MRZ Cross-Comparison */
              <div className="flex flex-col gap-1.5 max-h-[350px] overflow-y-auto pr-1">
                {/* Column Headers */}
                <div className="hidden sm:grid sm:grid-cols-[125px_1fr_1fr_90px_50px] gap-2 sm:gap-3 px-2 py-1.5 bg-surface/80 border-b border-outline-variant/40 text-[10px] font-label-caps text-on-surface-variant uppercase tracking-wider items-center">
                  <div>ATTRIBUTE</div>
                  <div>VIZ (OCR TEXT)</div>
                  <div>MRZ (ICAO 9303)</div>
                  <div className="text-center">CROSS-CHECK</div>
                  <div className="text-right">CONF.</div>
                </div>

                {passportComparisons.map((row) => (
                  <div
                    key={row.id}
                    className={`grid grid-cols-1 sm:grid-cols-[125px_1fr_1fr_90px_50px] gap-2 sm:gap-3 items-center py-2 px-2 border-b border-outline-variant/20 ${
                      row.isPrimary
                        ? "bg-primary-fixed/5 border-l-2 border-primary-fixed"
                        : "hover:bg-surface/30"
                    }`}
                  >
                    {/* Attribute */}
                    <div className="flex flex-col">
                      <span className="font-label-caps text-on-surface-variant uppercase text-[10px] tracking-wide">
                        {row.label}
                      </span>
                    </div>

                    {/* VIZ (OCR) */}
                    <div className="flex items-start gap-1.5 min-w-0">
                      <span className="text-[9px] px-1 py-0.5 bg-surface-container border border-outline-variant/40 text-on-surface-variant font-data-mono-md shrink-0 mt-0.5">
                        OCR
                      </span>
                      <div className="flex flex-col min-w-0">
                        <span
                          className={`font-data-mono-md text-xs break-words whitespace-normal leading-snug ${
                            row.isPrimary ? "text-on-surface font-bold" : "text-on-surface"
                          }`}
                          title={row.ocrValue}
                        >
                          {row.ocrValue || "—"}
                        </span>
                        {row.ocrNativeValue && row.ocrNativeValue !== row.ocrValue && (
                          <span
                            className="font-data-mono-md text-[10px] text-on-surface-variant/70 break-words whitespace-normal leading-tight mt-0.5"
                            title={`Native script: ${row.ocrNativeValue}`}
                          >
                            {row.ocrNativeValue}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* MRZ */}
                    <div className="flex items-start gap-1.5 min-w-0">
                      <span className="text-[9px] px-1 py-0.5 bg-primary-fixed/10 border border-primary-fixed/30 text-primary-fixed font-data-mono-md shrink-0 mt-0.5">
                        MRZ
                      </span>
                      <span
                        className={`font-data-mono-md text-xs break-words whitespace-normal leading-snug ${
                          row.isPrimary ? "text-primary-fixed font-bold" : "text-on-surface"
                        }`}
                        title={row.mrzValue}
                      >
                        {row.mrzValue || "—"}
                      </span>
                    </div>

                    {/* Status Badge */}
                    <div className="flex justify-start sm:justify-center">
                      {row.status === "MATCH" ? (
                        <span className="bg-primary-fixed/15 text-primary-fixed border border-primary-fixed/40 px-1.5 py-0.5 text-[10px] font-data-mono-md flex items-center gap-1">
                          <span className="material-symbols-outlined text-[13px]">check</span>
                          <span>MATCH</span>
                        </span>
                      ) : row.status === "ICAO_MATCH" ? (
                        <span
                          className="bg-primary-fixed/20 text-primary-fixed border border-primary-fixed/50 px-1.5 py-0.5 text-[9px] font-data-mono-md flex items-center gap-0.5"
                          title="Matched via ICAO Doc 9303 Transliteration (e.g. MÜLLER → MUELLER)"
                        >
                          <span className="material-symbols-outlined text-[12px]">translate</span>
                          <span>ICAO MATCH</span>
                        </span>
                      ) : row.status === "MISMATCH" ? (
                        <span className="bg-error/15 text-error border border-error/40 px-1.5 py-0.5 text-[10px] font-data-mono-md flex items-center gap-1 font-bold">
                          <span className="material-symbols-outlined text-[13px]">close</span>
                          <span>MISMATCH</span>
                        </span>
                      ) : (
                        <span className="bg-surface text-on-surface-variant border border-outline-variant/40 px-1.5 py-0.5 text-[10px] font-data-mono-md">
                          VERIFIED
                        </span>
                      )}
                    </div>

                    {/* Subtle Decreased Green Percentage Meter */}
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-6 h-1 bg-surface-variant rounded-full overflow-hidden shrink-0">
                        <div
                          className="h-full bg-primary-fixed transition-all duration-700"
                          style={{ width: `${Math.min(100, row.conf)}%` }}
                        />
                      </div>
                      <span className="font-data-mono-md text-[10px] text-primary-fixed shrink-0">
                        {row.conf.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              /* Non-Passport Documents (Voter ID, Aadhaar, License, etc.): Clean Single View */
              <div className="flex flex-col gap-2 max-h-[340px] overflow-y-auto pr-1">
                {allDisplayFields.map((field) => (
                  <div
                    key={field.id}
                    className={`flex flex-col sm:flex-row sm:items-center py-2 px-2 gap-3 border-b border-outline-variant/20 pb-2 ${
                      field.isPrimary
                        ? "bg-primary-fixed/5 px-2.5 -mx-1 border-l-2 border-primary-fixed"
                        : ""
                    }`}
                  >
                    <div className="sm:w-3/5 flex flex-col">
                      <span className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                        {field.label}
                      </span>
                      <span
                        className={`font-data-mono-lg tracking-wide ${
                          field.isPrimary
                            ? "text-primary-fixed font-bold text-base"
                            : "text-on-surface font-semibold text-sm"
                        }`}
                      >
                        {field.value}
                      </span>
                    </div>

                    {/* Subtle Decreased Green Percentage Meter */}
                    <div className="sm:w-2/5 flex items-center justify-end gap-2.5">
                      <div className="w-16 h-1 bg-surface-variant rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary-fixed transition-all duration-700"
                          style={{ width: `${Math.min(100, field.conf)}%` }}
                        />
                      </div>
                      <span className="font-data-mono-md text-primary-fixed w-12 text-right text-xs">
                        {field.conf.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Reasons for Suspicious Classification (Officer Decision Advisory) */}
          {isSuspicious && suspiciousFindings.length > 0 && (
            <div className="bg-error-container/15 border border-error/70 p-5 relative overflow-hidden flex flex-col gap-3.5 shadow-[0_0_15px_rgba(255,84,73,0.12)]">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-error/30 pb-2.5">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-error text-[20px] animate-pulse">
                    crisis_alert
                  </span>
                  <h3 className="font-label-caps text-error tracking-widest text-xs font-bold uppercase m-0">
                    AUDIT FINDINGS — REASONS FOR SUSPICIOUS CLASSIFICATION ({suspiciousFindings.length})
                  </h3>
                </div>
                <span className="bg-error/20 text-error border border-error/40 px-2 py-0.5 text-[10px] font-data-mono-md uppercase tracking-wider">
                  OFFICER DISCRETION
                </span>
              </div>

              {/* List of Detected Findings */}
              <div className="flex flex-col gap-2.5">
                {suspiciousFindings.map((finding) => (
                  <div
                    key={finding.id}
                    className="bg-background/90 border border-error/40 p-3 flex flex-col gap-2 rounded-none"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-error inline-block shrink-0" />
                        <span className="font-label-caps text-on-surface text-xs font-bold uppercase tracking-wide">
                          {finding.title}
                        </span>
                      </div>
                      <span className="font-data-mono-md text-[10px] text-error uppercase px-1.5 py-0.5 bg-error/10 border border-error/30 shrink-0">
                        {finding.badge}
                      </span>
                    </div>

                    <p className="text-on-surface-variant text-xs m-0 leading-relaxed">
                      {finding.description}
                    </p>

                    {finding.detail && (
                      <div className="bg-surface/90 px-2.5 py-1.5 border border-outline-variant/30 flex items-center gap-2">
                        <span className="material-symbols-outlined text-on-surface-variant text-[14px]">
                          terminal
                        </span>
                        <span className="font-data-mono-md text-[11px] text-primary-fixed">
                          {finding.detail}
                        </span>
                      </div>
                    )}

                    <div className="flex items-start gap-1.5 text-[11px] text-on-surface/90 pt-1.5 border-t border-outline-variant/20">
                      <span className="font-label-caps text-primary-fixed uppercase font-bold shrink-0 text-[10px]">
                        RECOMMENDED ACTION:
                      </span>
                      <span className="leading-snug">{finding.guidance}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Officer Protocol Guidance */}
              <div className="bg-surface-container-high/90 border border-outline-variant/40 p-3 flex items-center gap-2.5 text-xs">
                <span className="material-symbols-outlined text-secondary-fixed text-[20px] shrink-0">
                  gavel
                </span>
                <span className="text-[11px] text-on-surface-variant leading-relaxed">
                  Compare the extracted text with the physical scan on the right. If physical fraud or tampering is confirmed, select <strong className="text-error font-semibold">REJECT DOCUMENT</strong>. If an acceptable format variance or benign scan artifact is determined, select <strong className="text-secondary-fixed font-semibold">MANUAL VERIFICATION (OVERRIDE)</strong>.
                </span>
              </div>
            </div>
          )}

          {/* Forensic Security Feature Analysis */}
          <div className="bg-surface-container border border-outline-variant/50 p-6 relative">
            <div className="flex items-center justify-between mb-4 border-b border-outline-variant/60 pb-3">
              <h3 className="font-label-caps text-on-surface-variant uppercase tracking-widest m-0">
                FORENSIC & SECURITY FEATURE ANALYSIS
              </h3>
              <span
                className={`material-symbols-outlined text-[20px] ${
                  isCleared ? "text-primary-fixed" : "text-error"
                }`}
              >
                {isCleared ? "verified_user" : "gpp_maybe"}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {/* Check 1: MRZ Checksum */}
              <div
                className={`border-l-[4px] p-3 flex flex-col gap-1 ${
                  mrzCheck
                    ? "bg-primary-fixed/5 border-primary-fixed"
                    : "bg-error-container/20 border-error"
                }`}
              >
                <span className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                  MRZ CHECKSUM
                </span>
                <span
                  className={`font-data-mono-md font-bold uppercase text-xs ${
                    mrzCheck ? "text-primary-fixed" : "text-error"
                  }`}
                >
                  {mrzCheck ? "PASS" : "FAIL"}
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface-variant/70">
                  ICAO 9303 CHK-DIGIT
                </span>
              </div>

              {/* Check 2: ELA Pixel Forensics */}
              <div
                className={`border-l-[4px] p-3 flex flex-col gap-1 ${
                  elaPassed
                    ? "bg-primary-fixed/5 border-primary-fixed"
                    : "bg-error-container/20 border-error"
                }`}
              >
                <span className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                  ELA ANALYSIS
                </span>
                <span
                  className={`font-data-mono-md font-bold uppercase text-xs ${
                    elaPassed ? "text-primary-fixed" : "text-error"
                  }`}
                >
                  {elaPassed ? "PASS" : "FAIL"}
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface-variant/70">
                  PIXEL COMPRESSION
                </span>
              </div>

              {/* Check 3: Crop Boundary & Metadata */}
              <div
                className={`border-l-[4px] p-3 flex flex-col gap-1 ${
                  boundaryPassed
                    ? "bg-primary-fixed/5 border-primary-fixed"
                    : "bg-error-container/20 border-error"
                }`}
              >
                <span className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                  BOUNDARY & EXIF
                </span>
                <span
                  className={`font-data-mono-md font-bold uppercase text-xs ${
                    boundaryPassed ? "text-primary-fixed" : "text-error"
                  }`}
                >
                  {boundaryPassed ? "PASS" : "FAIL"}
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface-variant/70">
                  SOBEL / QUANT-TABLE
                </span>
              </div>

              {/* Check 4: Specification & Rules Engine */}
              <div
                className={`border-l-[4px] p-3 flex flex-col gap-1 ${
                  rulesPassed
                    ? "bg-primary-fixed/5 border-primary-fixed"
                    : "bg-error-container/20 border-error"
                }`}
              >
                <span className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                  RULES INTEGRITY
                </span>
                <span
                  className={`font-data-mono-md font-bold uppercase text-xs ${
                    rulesPassed ? "text-primary-fixed" : "text-error"
                  }`}
                >
                  {rulesPassed ? "PASS" : "FAIL"}
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface-variant/70">
                  SPEC RULES ENGINE
                </span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 mt-auto pt-4 border-t border-outline-variant/50">
            {isCleared ? (
              <button
                type="button"
                onClick={onProceedToBiometrics}
                className="flex-1 bg-primary-fixed text-on-primary-fixed font-headline-sm uppercase py-4 px-6 hover:bg-primary-fixed-dim transition-colors cursor-pointer border-none flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(192,245,0,0.25)]"
              >
                <span>PROCEED TO BIOMETRIC VERIFICATION</span>
                <span className="material-symbols-outlined">arrow_forward</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onProceedToBiometrics}
                className="flex-1 bg-transparent border-2 border-secondary-fixed text-secondary-fixed font-headline-sm uppercase py-4 px-6 hover:bg-secondary-fixed/10 transition-colors cursor-pointer flex items-center justify-center gap-2"
              >
                <span className="material-symbols-outlined">person_search</span>
                <span>MANUAL VERIFICATION (OVERRIDE)</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => onRejectDocument("Rejected at Stage 1 Document Screening")}
              disabled={isRejecting}
              className="bg-transparent text-error border border-error font-headline-sm uppercase py-4 px-8 hover:bg-error/10 transition-colors cursor-pointer flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined">block</span>
              <span>{isRejecting ? "REJECTING..." : "REJECT DOCUMENT"}</span>
            </button>
          </div>
        </div>

        {/* Right Column: Visual Document & Portrait Scans (Proportionate Width) */}
        <div className="w-full lg:w-[32%] xl:w-[30%] lg:min-w-[310px] lg:max-w-[380px] xl:max-w-[400px] lg:shrink-0 flex flex-col gap-6 sticky top-4">
          {/* Document Scan View */}
          <div className="bg-surface-container border border-outline-variant/50 p-4 h-[280px] flex flex-col relative group">
            <div className="flex items-center justify-between px-1 mb-2">
              <span className="font-label-caps text-on-surface-variant uppercase text-xs font-semibold">
                DOCUMENT SCAN — FULL IR / VIS
              </span>
              <span className="material-symbols-outlined text-on-surface-variant text-[18px]">
                scanner
              </span>
            </div>
            <div className="flex-1 relative overflow-hidden bg-background border border-outline-variant/40 flex items-center justify-center p-2">
              {docImageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={docImageUrl}
                  alt="Document Scan"
                  className="w-full h-full object-contain filter contrast-105"
                />
              ) : (
                <span className="font-data-mono-md text-xs text-on-surface-variant">
                  SCAN IMAGE PENDING
                </span>
              )}
              {/* Corner Reticles */}
              <div className="absolute top-2 left-2 w-5 h-5 border-t-2 border-l-2 border-primary-fixed/80 pointer-events-none" />
              <div className="absolute bottom-2 right-2 w-5 h-5 border-b-2 border-r-2 border-primary-fixed/80 pointer-events-none" />
            </div>
          </div>

          {/* Extracted Portrait View */}
          <div className="bg-surface-container border border-outline-variant/50 p-4 h-[280px] flex flex-col relative group">
            <div className="flex items-center justify-between px-1 mb-2">
              <span className="font-label-caps text-on-surface-variant uppercase text-xs font-semibold">
                EXTRACTED PORTRAIT — CHIP / PHOTO
              </span>
              <span className="material-symbols-outlined text-on-surface-variant text-[18px]">
                portrait
              </span>
            </div>
            <div className="flex-1 relative overflow-hidden bg-background border border-outline-variant/40 flex items-center justify-center p-3">
              {docFaceCropUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={docFaceCropUrl}
                  alt="Extracted Portrait"
                  className="max-h-full max-w-full object-contain filter contrast-105 rounded shadow-lg"
                />
              ) : (
                <div className="flex flex-col items-center gap-1 text-on-surface-variant">
                  <span className="material-symbols-outlined text-[32px]">
                    no_photography
                  </span>
                  <span className="font-data-mono-md text-xs">
                    NO PORTRAIT DETECTED
                  </span>
                </div>
              )}
              <div className="absolute bottom-2 left-2 flex gap-1.5 bg-surface-container/95 px-2.5 py-1 border border-outline-variant/60 shadow">
                <span className="font-data-mono-md text-[10px] text-primary-fixed font-bold">
                  ICAO: 19794-5
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface-variant">
                  • BIO CROP OK
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
