"use client";

import React, { useState, useEffect } from "react";
import { SidebarNav } from "../../../components/SidebarNav";
import { HeaderBar } from "../../../components/HeaderBar";
import { RequireRole } from "../../../lib/auth/RequireRole";
import {
  FileCode,
  Sliders,
  Play,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Download,
  RotateCcw,
  Search,
  Layers,
  Copy,
  Check,
  RefreshCw,
  Globe,
} from "lucide-react";

interface PolicyDefinition {
  id: string;
  label: string;
  category: "universal" | "regional";
  version: string;
  defaultPayload: Record<string, string>;
}

const POLICY_DEFINITIONS: PolicyDefinition[] = [
  // Universal Document Schemas
  {
    id: "passport",
    label: "passport_rules.yaml",
    category: "universal",
    version: "v4.3",
    defaultPayload: {
      passport_number: "Z1234567",
      date_of_expiry: "2030-10-15",
      date_of_birth: "1990-05-20",
      nationality: "IND",
    },
  },
  {
    id: "driving_license",
    label: "driving_license_rules.yaml",
    category: "universal",
    version: "v2.5",
    defaultPayload: {
      license_number: "DL-1420110012345",
      name: "RAJESH KUMAR",
      date_of_birth: "1988-03-12",
      date_of_expiry: "2034-03-11",
      vehicle_class: "LMV, MCWG",
      issuing_authority: "DL RTO DELHI",
    },
  },
  {
    id: "national_id",
    label: "national_id_rules.yaml",
    category: "universal",
    version: "v3.1",
    defaultPayload: {
      id_number: "5421 8901 2345",
      date_of_birth: "1995-11-04",
      nationality: "IND",
    },
  },
  {
    id: "visa",
    label: "visa_rules.yaml",
    category: "universal",
    version: "v2.0",
    defaultPayload: {
      visa_number: "V12345678",
      entry_validity: "2027-12-31",
      stay_duration: "90 days",
    },
  },
  {
    id: "permit",
    label: "permit_rules.yaml",
    category: "universal",
    version: "v1.9",
    defaultPayload: {
      permit_number: "IN-NP-2026-8842",
      name: "RISHABH SHARMA",
      permit_type: "CROSS-BORDER ENTRY PERMIT",
      issuing_authority: "BUREAU OF IMMIGRATION ICP",
      valid_until: "2027-12-28",
    },
  },
  {
    id: "pan_card",
    label: "pan_card_rules.yaml",
    category: "universal",
    version: "v2.2",
    defaultPayload: {
      pan_number: "ABCDE1234F",
      date_of_birth: "1991-08-19",
    },
  },
  {
    id: "voter_id",
    label: "voter_id_rules.yaml",
    category: "universal",
    version: "v2.3",
    defaultPayload: {
      voter_id_number: "ABC1234567",
      date_of_birth: "1993-02-14",
    },
  },

  // Regional Country-Specific Rule Sets
  {
    id: "IND",
    label: "IND.yaml (India)",
    category: "regional",
    version: "v1.0",
    defaultPayload: {
      passport_number: "A7654321",
      date_of_expiry: "2032-05-15",
      date_of_birth: "1985-06-10",
      nationality: "IND",
    },
  },
  {
    id: "NP",
    label: "NP.yaml (Nepal)",
    category: "regional",
    version: "v1.2",
    defaultPayload: {
      id_number: "05-02-80-12345",
      date_of_birth: "1988-06-20",
      nationality: "NPL",
    },
  },
  {
    id: "BD",
    label: "BD.yaml (Bangladesh)",
    category: "regional",
    version: "v1.3",
    defaultPayload: {
      id_number: "19801234567890123",
      date_of_birth: "1980-04-14",
      nationality: "BGD",
    },
  },
  {
    id: "BT",
    label: "BT.yaml (Bhutan)",
    category: "regional",
    version: "v1.1",
    defaultPayload: {
      id_number: "12345678901",
      date_of_birth: "1994-09-08",
      nationality: "BTN",
    },
  },
  {
    id: "MM",
    label: "MM.yaml (Myanmar)",
    category: "regional",
    version: "v1.1",
    defaultPayload: {
      id_number: "12/MAGANA(N)012345",
      date_of_birth: "1991-03-22",
      nationality: "MMR",
    },
  },
];

interface SandboxRuleResult {
  rule_name: string;
  passed: boolean;
  detail: string;
  severity?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function RulesAndThresholdAdminPage() {
  const [selectedDocType, setSelectedDocType] = useState("passport");
  const [yamlContent, setYamlContent] = useState("");
  const [loadingYaml, setLoadingYaml] = useState(true);
  const [copied, setCopied] = useState(false);

  // Model thresholds
  const [arcFaceThreshold, setArcFaceThreshold] = useState(0.35);
  const [rekognitionThreshold, setRekognitionThreshold] = useState(90);
  const [elaThreshold, setElaThreshold] = useState(0.25);
  const [livenessEarThreshold, setLivenessEarThreshold] = useState(0.70);

  // Live Sandbox
  const [sandboxPayload, setSandboxPayload] = useState("");
  const [sandboxEvaluating, setSandboxEvaluating] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<{
    passed: boolean;
    failed_rules: string[];
    rule_results: SandboxRuleResult[];
  } | null>(null);

  // Set default payload when doc type changes
  useEffect(() => {
    const policy = POLICY_DEFINITIONS.find((p) => p.id === selectedDocType);
    if (policy) {
      setSandboxPayload(JSON.stringify(policy.defaultPayload, null, 2));
      setSandboxResult(null);
    }
  }, [selectedDocType]);

  // Fetch real YAML rules file from backend
  const fetchYamlRules = async (docType: string) => {
    setLoadingYaml(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/validation/rules/${docType}`);
      if (res.ok) {
        const data = await res.json();
        setYamlContent(data.yaml_content || "");
      } else {
        setYamlContent("# Error loading rules file from server");
      }
    } catch (err) {
      console.error("Failed to load YAML rules:", err);
      setYamlContent("# Connection failed to validation service");
    } finally {
      setLoadingYaml(false);
    }
  };

  useEffect(() => {
    fetchYamlRules(selectedDocType);
  }, [selectedDocType]);

  // Run live rule evaluation in sandbox
  const handleRunSandbox = async () => {
    setSandboxEvaluating(true);
    try {
      const parsed = JSON.parse(sandboxPayload);
      const fieldArray = Array.isArray(parsed)
        ? parsed
        : Object.entries(parsed).map(([k, v]) => ({
            field_name: k,
            field_value: String(v),
            confidence: 0.99,
            extraction_method: "ocr",
          }));

      const activePolicy = POLICY_DEFINITIONS.find((p) => p.id === selectedDocType);
      const isRegional = activePolicy?.category === "regional";

      let res: Response;
      if (isRegional) {
        // Evaluate via regional validation endpoint
        res = await fetch(`${API_BASE_URL}/api/v1/validation/regional-validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nationality: selectedDocType,
            document_type: parsed.passport_number ? "passport" : "national_id",
            fields: fieldArray,
          }),
        });
      } else {
        // Evaluate via universal validation endpoint (fires both universal + regional)
        res = await fetch(`${API_BASE_URL}/api/v1/validation/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_type: selectedDocType,
            fields: fieldArray,
          }),
        });
      }

      if (res.ok) {
        const data = await res.json();
        setSandboxResult({
          passed: data.passed,
          failed_rules: data.failed_rules || [],
          rule_results: data.rule_results || [],
        });
      } else {
        setSandboxResult({
          passed: false,
          failed_rules: [`Server returned status ${res.status}`],
          rule_results: [],
        });
      }
    } catch (err) {
      console.error("Sandbox validation failed:", err);
      setSandboxResult({
        passed: false,
        failed_rules: ["Invalid JSON syntax in test payload."],
        rule_results: [],
      });
    } finally {
      setSandboxEvaluating(false);
    }
  };

  const copyYaml = () => {
    navigator.clipboard.writeText(yamlContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const universalPolicies = POLICY_DEFINITIONS.filter((p) => p.category === "universal");
  const regionalPolicies = POLICY_DEFINITIONS.filter((p) => p.category === "regional");

  return (
    <RequireRole roles={["admin", "supervisor"]}>
      <div className="min-h-screen flex bg-[#0B0C0E] text-[#e3e2e5]">
        <SidebarNav />

        <div className="flex-1 flex flex-col min-w-0">
          <HeaderBar
            title="RULES & THRESHOLD ADMINISTRATION"
            subtitle="DECLARATIVE POLICY REPOSITORY & INFERENCE GATES"
          />

          <main className="flex-1 flex flex-col w-full bg-[#0B0C0E]">
            {/* TOP TICKER STRIP */}
            <div className="w-full bg-[#0D0E10] px-6 py-2 flex flex-wrap items-center justify-between gap-2 border-b border-[#2D3135]">
              <div className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-[#c0f500] animate-pulse"></span>
                <span className="font-mono text-xs font-bold text-[#c0f500] tracking-wider uppercase">
                  SECURITY POLICY CONSOLE
                </span>
                <span className="text-[#8e9479] text-xs font-mono">|</span>
                <span className="text-[#8e9479] text-xs font-mono">
                  HOT-RELOAD ENGINE: <strong className="text-white">ACTIVE (ZERO RESTART)</strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-[#8e9479]">
                  SUPPORTED REGIONS: <strong>5 COUNTRIES (IND, NP, BD, BT, MM)</strong>
                </span>
              </div>
            </div>

            {/* 3-COLUMN HIGH-DENSITY WORKSPACE */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 flex-1">
              {/* LEFT COLUMN: SCHEMA & POLICY SELECTOR (3 Cols) */}
              <div className="lg:col-span-3 bg-[#0D0E10] border-r border-[#2D3135] flex flex-col justify-between p-4 overflow-y-auto max-h-[calc(100vh-100px)]">
                <div>
                  {/* Universal Policies */}
                  <div className="text-[10px] font-mono uppercase text-[#8e9479] tracking-wider mb-2 font-bold flex items-center justify-between">
                    <span>UNIVERSAL SCHEMAS</span>
                    <span>{universalPolicies.length} POLICIES</span>
                  </div>

                  <div className="space-y-1 mb-5">
                    {universalPolicies.map((dt) => {
                      const isSelected = selectedDocType === dt.id;
                      return (
                        <div
                          key={dt.id}
                          onClick={() => setSelectedDocType(dt.id)}
                          className={`p-2.5 border flex items-center justify-between transition-all cursor-pointer ${
                            isSelected
                              ? "bg-[#1F2022] border-[#c0f500] text-white"
                              : "bg-[#141517] border-[#2D3135] text-[#c4caac] hover:border-[#8e9479]/50 hover:bg-[#1B1C1E]"
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <FileCode
                              size={14}
                              className={isSelected ? "text-[#c0f500]" : "text-[#8e9479]"}
                            />
                            <span className="font-mono text-xs truncate font-bold">
                              {dt.label}
                            </span>
                          </div>
                          <span
                            className={`font-mono text-[9px] px-1.5 py-0.5 uppercase ${
                              isSelected
                                ? "bg-[#c0f500] text-[#121315] font-bold"
                                : "bg-[#292a2c] text-[#8e9479]"
                            }`}
                          >
                            {dt.version}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Regional Country Policies */}
                  <div className="text-[10px] font-mono uppercase text-[#8e9479] tracking-wider mb-2 font-bold flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Globe size={11} className="text-[#c0f500]" />
                      REGIONAL POLICIES
                    </span>
                    <span>{regionalPolicies.length} JURISDICTIONS</span>
                  </div>

                  <div className="space-y-1">
                    {regionalPolicies.map((dt) => {
                      const isSelected = selectedDocType === dt.id;
                      return (
                        <div
                          key={dt.id}
                          onClick={() => setSelectedDocType(dt.id)}
                          className={`p-2.5 border flex items-center justify-between transition-all cursor-pointer ${
                            isSelected
                              ? "bg-[#1F2022] border-[#c0f500] text-white"
                              : "bg-[#141517] border-[#2D3135] text-[#c4caac] hover:border-[#8e9479]/50 hover:bg-[#1B1C1E]"
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <Globe
                              size={14}
                              className={isSelected ? "text-[#c0f500]" : "text-[#8e9479]"}
                            />
                            <span className="font-mono text-xs truncate font-bold">
                              {dt.label}
                            </span>
                          </div>
                          <span
                            className={`font-mono text-[9px] px-1.5 py-0.5 uppercase ${
                              isSelected
                                ? "bg-[#c0f500] text-[#121315] font-bold"
                                : "bg-[#292a2c] text-[#8e9479]"
                            }`}
                          >
                            {dt.version}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Schema Notes */}
                  <div className="mt-5 p-3 bg-[#141517] border border-[#2D3135] font-mono text-xs text-[#8e9479] space-y-1.5">
                    <div className="text-white font-bold uppercase text-[10px]">
                      HOT-RELOAD ENGINE
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Changes in YAML rules on disk take effect on the very next screening pipeline pass without server restarts.
                    </p>
                  </div>
                </div>
              </div>

              {/* MIDDLE COLUMN: LIVE YAML EDITOR (5 Cols) */}
              <div className="lg:col-span-5 bg-[#121315] border-r border-[#2D3135] flex flex-col">
                <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border-b border-[#2D3135]">
                  <span className="font-mono text-xs font-bold text-white uppercase">
                    ACTIVE DECLARATIVE RULESET: {selectedDocType.toUpperCase()}
                  </span>
                  <span className="font-mono text-[10px] text-[#8e9479]">
                    READ-ONLY DISK MIRROR
                  </span>
                </div>

                <div className="relative flex-1 p-4 bg-[#0A0B0D] font-mono text-xs overflow-auto max-h-[calc(100vh-160px)]">
                  {loadingYaml ? (
                    <div className="flex items-center justify-center h-48 text-[#8e9479]">
                      <RefreshCw size={18} className="animate-spin mr-2 text-[#c0f500]" />
                      <span>Reading policy from server...</span>
                    </div>
                  ) : (
                    <pre className="text-[#c4caac] whitespace-pre-wrap leading-relaxed">
                      {yamlContent}
                    </pre>
                  )}

                  <button
                    onClick={copyYaml}
                    className="absolute top-3 right-3 px-2 py-1 bg-[#141517] border border-[#2D3135] text-[#8e9479] hover:text-white hover:border-[#c0f500] font-mono text-[10px] flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    {copied ? <Check size={12} className="text-[#c0f500]" /> : <Copy size={12} />}
                    <span>{copied ? "COPIED" : "COPY YAML"}</span>
                  </button>
                </div>
              </div>

              {/* RIGHT COLUMN: MODEL GATES & LIVE SANDBOX (4 Cols) */}
              <div className="lg:col-span-4 bg-[#0D0E10] p-4 flex flex-col justify-between overflow-y-auto max-h-[calc(100vh-100px)]">
                {/* 1. MODEL THRESHOLDS */}
                <div>
                  <div className="text-[10px] font-mono uppercase text-[#8e9479] tracking-wider mb-3 font-bold flex items-center gap-1.5">
                    <Sliders size={13} className="text-[#c0f500]" />
                    <span>ML INFERENCE GATES</span>
                  </div>

                  <div className="space-y-3 bg-[#141517] border border-[#2D3135] p-3 mb-4">
                    <div>
                      <div className="flex justify-between text-xs font-mono mb-1">
                        <span className="text-[#c4caac]">ArcFace Cosine Gate</span>
                        <span className="text-[#c0f500] font-bold">{arcFaceThreshold}</span>
                      </div>
                      <input
                        type="range"
                        min="0.2"
                        max="0.8"
                        step="0.05"
                        value={arcFaceThreshold}
                        onChange={(e) => setArcFaceThreshold(parseFloat(e.target.value))}
                        className="w-full accent-[#c0f500] cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-xs font-mono mb-1">
                        <span className="text-[#c4caac]">AWS Rekognition Conf.</span>
                        <span className="text-[#c0f500] font-bold">{rekognitionThreshold}%</span>
                      </div>
                      <input
                        type="range"
                        min="70"
                        max="99"
                        step="1"
                        value={rekognitionThreshold}
                        onChange={(e) => setRekognitionThreshold(parseInt(e.target.value))}
                        className="w-full accent-[#c0f500] cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-xs font-mono mb-1">
                        <span className="text-[#c4caac]">Forensic ELA Threshold</span>
                        <span className="text-[#c0f500] font-bold">{elaThreshold}</span>
                      </div>
                      <input
                        type="range"
                        min="0.1"
                        max="0.5"
                        step="0.05"
                        value={elaThreshold}
                        onChange={(e) => setElaThreshold(parseFloat(e.target.value))}
                        className="w-full accent-[#c0f500] cursor-pointer"
                      />
                    </div>
                  </div>
                </div>

                {/* 2. LIVE EVALUATION SANDBOX */}
                <div className="pt-3 border-t border-[#2D3135] flex flex-col flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                      <Play size={14} className="text-[#c0f500]" />
                      RULE TEST SANDBOX
                    </span>
                    <button
                      onClick={handleRunSandbox}
                      disabled={sandboxEvaluating}
                      className="px-3 py-1 bg-[#c0f500] hover:bg-white text-[#121315] font-mono text-xs font-bold uppercase transition-colors cursor-pointer flex items-center gap-1 disabled:opacity-50"
                    >
                      <Play size={11} className={sandboxEvaluating ? "animate-spin" : ""} />
                      <span>{sandboxEvaluating ? "RUNNING..." : "EVALUATE"}</span>
                    </button>
                  </div>

                  <textarea
                    value={sandboxPayload}
                    onChange={(e) => setSandboxPayload(e.target.value)}
                    rows={6}
                    className="w-full bg-[#141517] border border-[#2D3135] p-3 font-mono text-xs text-[#c4caac] focus:border-[#c0f500] focus:outline-none mb-3 resize-none"
                    placeholder="Enter OCR fields JSON payload..."
                  />

                  {sandboxResult && (
                    <div
                      className={`p-3 border font-mono text-xs ${
                        sandboxResult.passed
                          ? "bg-[#161f00] border-[#c0f500] text-[#c0f500]"
                          : "bg-[#251010] border-[#ff3b30] text-[#ffdad6]"
                      }`}
                    >
                      <div className="font-bold flex items-center justify-between mb-2">
                        <div className="flex items-center gap-1.5">
                          {sandboxResult.passed ? (
                            <CheckCircle2 size={16} />
                          ) : (
                            <AlertTriangle size={16} className="text-[#ff3b30]" />
                          )}
                          <span>
                            VERDICT: {sandboxResult.passed ? "ALL RULES PASSED" : "VIOLATIONS DETECTED"}
                          </span>
                        </div>
                        <span className="text-[10px] opacity-80">
                          {sandboxResult.rule_results.length} RULES EVALUATED
                        </span>
                      </div>

                      {/* Detailed per-rule list with severity */}
                      <div className="space-y-1.5 text-[11px] max-h-48 overflow-y-auto">
                        {sandboxResult.rule_results.map((r, i) => (
                          <div
                            key={i}
                            className={`p-1.5 border flex items-start justify-between gap-2 ${
                              r.passed
                                ? "bg-[#141517]/60 border-[#2D3135] text-[#c4caac]"
                                : "bg-[#93000a]/20 border-[#ff3b30]/60 text-white"
                            }`}
                          >
                            <div className="min-w-0 flex-1">
                              <div className="font-bold flex items-center gap-1">
                                <span className={r.passed ? "text-[#c0f500]" : "text-[#ff3b30]"}>
                                  {r.passed ? "✓" : "✗"}
                                </span>
                                <span className="truncate">{r.rule_name}</span>
                              </div>
                              <div className="text-[10px] text-[#8e9479] truncate mt-0.5">
                                {r.detail}
                              </div>
                            </div>
                            {r.severity && (
                              <span
                                className={`text-[9px] px-1 py-0.2 uppercase font-bold shrink-0 ${
                                  r.severity === "critical"
                                    ? "bg-[#ff3b30]/20 text-[#ff3b30] border border-[#ff3b30]/50"
                                    : r.severity === "high"
                                    ? "bg-[#ff9500]/20 text-[#ff9500] border border-[#ff9500]/50"
                                    : "bg-[#292a2c] text-[#8e9479]"
                                }`}
                              >
                                {r.severity}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </RequireRole>
  );
}
