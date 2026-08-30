"use client";

import React, { useState } from "react";

interface AdminScanQueueProps {
  onInspectRow: (rowId: string) => void;
}

interface ScanRow {
  id: string;
  name: string;
  docType: string;
  riskBand: "low" | "medium" | "high";
  score: number;
  time: string;
  status: "Approved" | "Flagged" | "Denied" | "Scanning";
  avatar: string;
}

const INITIAL_QUEUE: ScanRow[] = [
  {
    id: "scan-001",
    name: "Jane Marie Miller",
    docType: "Passport (USA)",
    riskBand: "high",
    score: 84,
    time: "12:38 PM",
    status: "Flagged",
    avatar:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuBibx1YUmNiaerNSRHR1_TMX1n78o7sdOHzTR_bjklfZmWaW_FUhiQk4TiubSAm-56p2_BUD4s8D9xEnPiFckvei8mibCZQn46-Mm15dbWSj-sPe1uItmuxp0hqsEWfbLJraF8FwIq50_1y5Nf7DgPwaQAJAWmTOvseSByQ4tr1yNrnL0p81vfmdo_eA4De87WSG0PtZstLhRgEEDhYGqnt4uXFRpv2zmj97NRJPBCC52bdaPG8F4JDnA",
  },
  {
    id: "scan-002",
    name: "Arthur Pendelton",
    docType: "Passport (GBR)",
    riskBand: "low",
    score: 12,
    time: "12:34 PM",
    status: "Approved",
    avatar:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuBN9FRHAYajGLcEfbLyGyK8BRtStpPtx8Gc7ypEd7nla5_vbu2xb8j8q7iWM6JLMtD2gUJqt4pCGTop6zVr6BrlO0KeJR0E6GfVP00mDxCG1y9hJ6tBzxVWZj-KK2yN8C8eidMOKXcs4x7tFOpyniLLFUFQpkPXPQSnoAabcEvYI_lZmjF7iM9_Q6Mu_Fl5FS3SJjX_qUwIeUzFvOe3ecdFFb_1j2Zr-p0j1vWPrmm4OOYBIopRM-wbvA",
  },
  {
    id: "scan-003",
    name: "Elena Rostova",
    docType: "Visa Permit (CAN)",
    riskBand: "medium",
    score: 48,
    time: "12:28 PM",
    status: "Flagged",
    avatar:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCvB9jJ_EhP1hBEYlNk-TXQzaPMY9pXiabQFPttBwn5-fPfW0jCBJfAA6UT7dMgYOP_zir76kteaCnrhIHpwzfgAky2pKECRktcOAoNu-1Dq3MWj7MKCsSZfvbLlJwHDlTTa0h30G0RGvmPGRE_Y0d0u0tQm1mqFiOp8ClIH9WKet70BRN_GhSTpOl5mzNIaBya_9t7pbCk8rSiHoY9yElKcCdB0RkRRNlXvmG7JJszuoNQLzhINwGEiQ",
  },
  {
    id: "scan-004",
    name: "David K. Chen",
    docType: "Passport (SGP)",
    riskBand: "low",
    score: 8,
    time: "12:15 PM",
    status: "Approved",
    avatar:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCf1SmCJMoQh819R4Q1IzcM0cCDm0lFOr0Ez33T4J9gAOAwW6H_cJRAxImi22h3FV2KZZpefOE0cTbzWCbdC0YrfVfkstFoyRcRC-fQrKVaghlqF0pph-QOwF9fFo4YsbAPz2XrV_DwPU9J9YC7G-6Og42vLjwRjRqQG1YZu_HCw9jNzrnjXT4qHUnA4F1PeU3yAVEHeii2_fkJmVXBY7xAeYswO9kKr-f-8iz7ozeM7-angXwShZUMhQ",
  },
  {
    id: "scan-005",
    name: "Marcus Vance",
    docType: "Passport (AUS)",
    riskBand: "high",
    score: 91,
    time: "11:58 AM",
    status: "Denied",
    avatar:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuDaPXLQeRwK5DanFB6hgS1fM15a-W0MwLmDzio7iGvHxvXA2Tu2EsKC0R-sFgMngxz1eYu13GU-oLgyzz9oMHTtRTKB2bkvPIQ79J1CxpUdUc6ac7r05Bc_HZnvwafHeYxcdNuTSMjEWNmcegGAQO5gCU6oeg2H58ipNNeqejfrGfruVWY7YxN1nRtysn3H5j9EZxeCnZ5qtL6utC_mkq-bWO_zBoc0kvsSkxhkBqZW1DJdmhehun8OXA",
  },
];

export const AdminScanQueue: React.FC<AdminScanQueueProps> = ({ onInspectRow }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRisk, setFilterRisk] = useState<string>("all");

  const filteredQueue = INITIAL_QUEUE.filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.docType.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRisk = filterRisk === "all" || item.riskBand === filterRisk;
    return matchesSearch && matchesRisk;
  });

  return (
    <div className="flex-1 w-full max-w-[1440px] mx-auto px-6 py-10 flex flex-col">
      {/* Header Section */}
      <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-[#d97757] uppercase tracking-wider mb-2">
            <span>Operational Control</span>
            <span>·</span>
            <span>Live Checkpoint Alpha-7</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-[#2B2622] tracking-tight">
            Scan Queue &amp; Audit Log
          </h1>
          <p className="text-base text-[#55433d] mt-1">
            Real-time checkpoint screening pipeline and cryptographic ledger logs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#88726c] text-lg">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search ID or Name..."
              className="pl-10 pr-4 py-2.5 bg-[#FAF8F5] border border-[#E8E2D9] rounded-xl focus:border-[#d97757] text-xs font-medium text-[#2B2622] outline-none transition-colors w-64"
            />
          </div>

          <select
            value={filterRisk}
            onChange={(e) => setFilterRisk(e.target.value)}
            className="px-3 py-2.5 bg-[#FAF8F5] border border-[#E8E2D9] rounded-xl text-xs font-bold text-[#55433d] outline-none cursor-pointer"
          >
            <option value="all">All Risk Bands</option>
            <option value="low">Low Risk Only</option>
            <option value="medium">Medium Risk</option>
            <option value="high">High Risk Flags</option>
          </select>
        </div>
      </div>

      {/* Metrics Bento Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Cleared Today */}
        <div className="bg-[#FAF8F5] rounded-2xl p-6 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-[#E5F3EA] flex items-center justify-center text-[#2F8F5B]">
              <span className="material-symbols-outlined">check_circle</span>
            </div>
            <span className="text-xs font-bold text-[#655d54] uppercase tracking-wider">
              Cleared Today
            </span>
          </div>
          <div className="text-4xl font-extrabold text-[#2B2622]">1,248</div>
          <span className="text-xs text-[#2F8F5B] font-bold mt-1 block">
            ↑ 98.2% Auto-Approved
          </span>
        </div>

        {/* Pending Review */}
        <div className="bg-[#FAF8F5] rounded-2xl p-6 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-[#FBF0D6] flex items-center justify-center text-[#B8860B]">
              <span className="material-symbols-outlined">pending_actions</span>
            </div>
            <span className="text-xs font-bold text-[#655d54] uppercase tracking-wider">
              Pending Review
            </span>
          </div>
          <div className="text-4xl font-extrabold text-[#2B2622]">12</div>
          <span className="text-xs text-[#B8860B] font-bold mt-1 block">
            Average hold: 2.4 mins
          </span>
        </div>

        {/* High Risk Flags */}
        <div className="bg-[#FAF8F5] rounded-2xl p-6 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-[#FBE7D8] flex items-center justify-center text-[#C1652E]">
              <span className="material-symbols-outlined">warning</span>
            </div>
            <span className="text-xs font-bold text-[#655d54] uppercase tracking-wider">
              High Risk Flags
            </span>
          </div>
          <div className="text-4xl font-extrabold text-[#C1652E]">3</div>
          <span className="text-xs text-[#C1652E] font-bold mt-1 block">
            Requires Supervisor Escort
          </span>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-[#FAF8F5] rounded-2xl shadow-[0px_4px_20px_rgba(43,38,34,0.04)] border border-[#E8E2D9] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#f0ede9] border-b border-[#E8E2D9]">
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider">
                  Traveler Name
                </th>
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider">
                  Document Type
                </th>
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider">
                  Risk Score
                </th>
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-4 text-xs font-bold text-[#655d54] uppercase tracking-wider text-right">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E2D9] text-sm text-[#2B2622]">
              {filteredQueue.map((row) => (
                <tr
                  key={row.id}
                  className="hover:bg-white transition-colors cursor-pointer"
                  onClick={() => onInspectRow(row.id)}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <img
                        alt={row.name}
                        className="w-9 h-9 rounded-full object-cover border border-[#E8E2D9]"
                        src={row.avatar}
                      />
                      <div>
                        <div className="font-bold text-sm text-[#2B2622]">{row.name}</div>
                        <div className="text-[11px] text-[#88726c]">{row.id}</div>
                      </div>
                    </div>
                  </td>

                  <td className="px-6 py-4 text-xs font-medium text-[#55433d]">{row.docType}</td>

                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                        row.riskBand === "low"
                          ? "bg-[#E5F3EA] text-[#2F8F5B]"
                          : row.riskBand === "medium"
                          ? "bg-[#FBF0D6] text-[#B8860B]"
                          : "bg-[#FBE7D8] text-[#C1652E]"
                      }`}
                    >
                      <span>{row.score}/100</span>
                      <span className="text-[10px] capitalize">({row.riskBand})</span>
                    </span>
                  </td>

                  <td className="px-6 py-4 text-xs text-[#655d54] font-medium">{row.time}</td>

                  <td className="px-6 py-4">
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
                        row.status === "Approved"
                          ? "bg-[#E5F3EA] text-[#2F8F5B]"
                          : row.status === "Flagged"
                          ? "bg-[#FBF0D6] text-[#B8860B]"
                          : "bg-[#FBE3E3] text-[#C13B3B]"
                      }`}
                    >
                      {row.status}
                    </span>
                  </td>

                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onInspectRow(row.id);
                      }}
                      className="px-3.5 py-1.5 rounded-lg border border-[#E8E2D9] text-xs font-bold text-[#d97757] hover:bg-[#d97757] hover:text-white transition-colors cursor-pointer"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
