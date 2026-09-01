"use client";

import React, { useState, useEffect } from "react";
import { api } from "../../lib/api/client";
import { MOCK_FRAUD_GRAPH, MOCK_CLUSTER_DETAIL } from "../../lib/api/mocks";
import type {
  FraudGraphData,
  FraudClusterNode,
  ClusterHistoryResponse,
} from "../../lib/api/types";
import { RiskBadge } from "../RiskBadge";
import {
  GitFork,
  AlertTriangle,
  ShieldAlert,
  RefreshCw,
} from "lucide-react";

export function FraudGraph() {
  const [selectedClusterId, setSelectedClusterId] = useState<string>(
    "7b2e2d1a-4122-4809-94fc-32490ab81234"
  );
  const [clusterDetail, setClusterDetail] =
    useState<ClusterHistoryResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedNode, setSelectedNode] = useState<FraudClusterNode | null>(null);

  const graphData: FraudGraphData = MOCK_FRAUD_GRAPH;

  useEffect(() => {
    if (!selectedClusterId) return;

    let isMounted = true;
    Promise.resolve().then(() => {
      if (isMounted) setLoadingDetail(true);
    });

    api
      .getClusterHistory(selectedClusterId)
      .then((res) => {
        if (isMounted) setClusterDetail(res);
      })
      .catch(() => {
        // Fallback to rich mock detail
        if (isMounted) setClusterDetail(MOCK_CLUSTER_DETAIL);
      })
      .finally(() => {
        if (isMounted) setLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedClusterId]);

  return (
    <div className="flex flex-col xl:flex-row gap-5 h-[calc(100vh-140px)] min-h-[640px]">
      {/* 1. Left / Top Node-Link Canvas (~65%) */}
      <div className="flex-1 bg-surface border border-border rounded-md flex flex-col overflow-hidden relative">
        {/* Graph Toolbar */}
        <div className="p-3.5 border-b border-border bg-surface-raised flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <GitFork size={16} className="text-brand" />
            <h2 className="font-display font-bold text-sm text-text uppercase tracking-tight">
              Cross-Checkpoint Identity Collision Network
            </h2>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-text-muted hidden sm:inline">Active Clusters:</span>
            <div className="flex gap-1">
              {graphData.clusters.map((c) => (
                <button
                  key={c.cluster_id}
                  onClick={() => {
                    setSelectedClusterId(c.cluster_id);
                    setSelectedNode(null);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                    selectedClusterId === c.cluster_id
                      ? "bg-brand text-bg font-bold"
                      : "bg-surface border border-border text-text-muted hover:text-text"
                  }`}
                >
                  {c.primary_name.split(" ")[0]}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Interactive SVG Network Graph */}
        <div className="flex-1 relative bg-bg overflow-auto p-4 flex items-center justify-center">
          {/* Subtle Grid background */}
          <div
            className="absolute inset-0 pointer-events-none opacity-20"
            style={{
              backgroundImage:
                "radial-gradient(#263025 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />

          <svg
            viewBox="0 0 1000 600"
            className="w-full h-full max-h-[580px] select-none"
          >
            {/* Defs for markers and gradients */}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="8"
                markerHeight="6"
                refX="14"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#8C978A" />
              </marker>
              <marker
                id="arrowhead-danger"
                markerWidth="8"
                markerHeight="6"
                refX="14"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#FF4545" />
              </marker>
            </defs>

            {/* Links */}
            {graphData.links.map((link, idx) => {
              const srcNode = graphData.nodes.find((n) => n.id === link.source);
              const tgtNode = graphData.nodes.find((n) => n.id === link.target);
              if (!srcNode || !tgtNode) return null;

              const isDanger =
                link.severity === "critical" || link.severity === "high";

              return (
                <g key={idx} className="group/link">
                  <line
                    x1={srcNode.x}
                    y1={srcNode.y}
                    x2={tgtNode.x}
                    y2={tgtNode.y}
                    stroke={isDanger ? "#FF4545" : "#263025"}
                    strokeWidth={isDanger ? 2.5 : 1.5}
                    strokeDasharray={
                      link.flagType === "impossible_travel_detected"
                        ? "5,5"
                        : undefined
                    }
                    className={
                      isDanger ? "animate-pulse" : "transition-colors"
                    }
                  />
                  {/* Link Label */}
                  <text
                    x={((srcNode.x || 0) + (tgtNode.x || 0)) / 2}
                    y={((srcNode.y || 0) + (tgtNode.y || 0)) / 2 - 8}
                    fill={isDanger ? "#FF8A3D" : "#8C978A"}
                    fontSize="10"
                    fontFamily="JetBrains Mono"
                    textAnchor="middle"
                    className="select-none bg-bg"
                  >
                    {link.label}
                  </text>
                </g>
              );
            })}

            {/* Nodes */}
            {graphData.nodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              const isPerson = node.type === "person";
              const isCP = node.type === "checkpoint";

              const color =
                node.riskBand === "critical"
                  ? "#FF4545"
                  : node.riskBand === "high"
                  ? "#FF8A3D"
                  : node.riskBand === "medium"
                  ? "#F5B942"
                  : isCP
                  ? "#8C978A"
                  : "#A6FF4D";

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={() => {
                    setSelectedNode(node);
                    if (node.clusterId) setSelectedClusterId(node.clusterId);
                  }}
                  className="cursor-pointer group/node"
                >
                  {/* Outer Glow on selection */}
                  {isSelected && (
                    <circle
                      r={isPerson ? 28 : 20}
                      fill="none"
                      stroke={color}
                      strokeWidth="2"
                      strokeDasharray="4,4"
                      className="animate-spin"
                    />
                  )}

                  {/* Base Circle / Rectangle */}
                  {isCP ? (
                    <rect
                      x="-14"
                      y="-14"
                      width="28"
                      height="28"
                      rx="4"
                      fill="#12160F"
                      stroke="#8C978A"
                      strokeWidth="2"
                    />
                  ) : (
                    <circle
                      r={isPerson ? 20 : 14}
                      fill="#12160F"
                      stroke={color}
                      strokeWidth={isPerson ? 3 : 2}
                      className="transition-transform duration-150 group-hover/node:scale-110"
                    />
                  )}

                  {/* Inner Label / Node Text */}
                  <text
                    y={isPerson ? 34 : 26}
                    fill="#F2F5F0"
                    fontSize={isPerson ? "12" : "10"}
                    fontFamily="JetBrains Mono"
                    fontWeight={isPerson ? "bold" : "normal"}
                    textAnchor="middle"
                    className="select-none pointer-events-none drop-shadow"
                  >
                    {node.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Graph Legend Overlay */}
          <div className="absolute bottom-3 left-3 bg-surface/90 backdrop-blur-xs border border-border rounded p-2.5 font-mono text-[10px] space-y-1 z-10">
            <div className="text-text-muted uppercase font-bold mb-1">
              Legend:
            </div>
            <div className="flex items-center gap-2 text-text">
              <span className="w-2.5 h-2.5 rounded-full bg-brand" />
              <span>Person Anchor</span>
            </div>
            <div className="flex items-center gap-2 text-text">
              <span className="w-2.5 h-2.5 rounded-full bg-risk-critical" />
              <span>Multi-Identity Passport Hit</span>
            </div>
            <div className="flex items-center gap-2 text-text">
              <span className="w-2.5 h-2.5 rounded-xs bg-text-muted" />
              <span>Border Checkpoint</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Right Detail Side Panel (~35%) */}
      <div className="w-full xl:w-[420px] bg-surface border border-border rounded-md flex flex-col overflow-hidden shrink-0">
        {/* Panel Header */}
        <div className="p-4 border-b border-border bg-surface-raised flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldAlert size={18} className="text-risk-critical" />
              <h3 className="font-display font-bold text-sm text-text uppercase">
                Cluster Dossier
              </h3>
            </div>
            <p className="font-mono text-[11px] text-text-muted mt-0.5 truncate max-w-[280px]">
              ID: {selectedClusterId}
            </p>
          </div>

          {clusterDetail && (
            <RiskBadge
              band={clusterDetail.highest_prior_risk_band || "critical"}
              score={clusterDetail.cross_checkpoint_risk * 100}
              size="sm"
            />
          )}
        </div>

        {/* Dossier Content */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4">
          {loadingDetail ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-text-muted">
              <RefreshCw size={20} className="animate-spin text-brand" />
              <span className="font-mono text-xs">
                Querying cross-checkpoint history...
              </span>
            </div>
          ) : clusterDetail ? (
            <>
              {/* Executive Summary */}
              <div className="p-3 rounded bg-risk-critical/10 border border-risk-critical/30 space-y-1.5">
                <div className="font-mono text-[10px] uppercase font-bold text-risk-critical flex items-center gap-1.5">
                  <AlertTriangle size={12} />
                  Threat Narrative:
                </div>
                <p className="font-body text-xs text-text leading-relaxed">
                  {clusterDetail.summary}
                </p>
              </div>

              {/* Multi-Identity Flags List */}
              <div className="space-y-2">
                <h4 className="font-mono text-[10px] uppercase text-text-muted tracking-wider">
                  Active Cross-Checkpoint Flags ({clusterDetail.flags.length})
                </h4>
                <div className="space-y-2">
                  {clusterDetail.flags.map((flag, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-bg border border-border space-y-1 text-xs"
                    >
                      <div className="flex items-center justify-between font-mono text-[10px]">
                        <span className="uppercase text-risk-critical font-bold">
                          {flag.flag_type.replace(/_/g, " ")}
                        </span>
                        <span className="text-text-muted">
                          {flag.timestamp
                            ? new Date(flag.timestamp).toLocaleTimeString()
                            : ""}
                        </span>
                      </div>
                      <p className="font-body text-text leading-snug">
                        {flag.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Linked Documents Cross-Table */}
              <div className="space-y-2 pt-2 border-t border-border">
                <h4 className="font-mono text-[10px] uppercase text-text-muted tracking-wider">
                  Associated Passport Records ({clusterDetail.documents.length})
                </h4>
                <div className="space-y-2">
                  {clusterDetail.documents.map((doc, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-surface-raised border border-border font-mono text-xs space-y-1"
                    >
                      <div className="flex justify-between items-center text-text font-bold">
                        <span>{doc.name || "UNKNOWN"}</span>
                        <RiskBadge
                          band={doc.risk_band || "medium"}
                          score={doc.risk_score}
                          size="sm"
                          showScore={false}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] text-text-muted">
                        <span>
                          Doc #{doc.document_number} ({doc.nationality})
                        </span>
                        <span>{doc.checkpoint_id}</span>
                      </div>
                      <div className="flex justify-between text-[10px] text-text-muted/80 pt-1 border-t border-border/60">
                        <span>
                          Biometric Match:{" "}
                          <strong className="text-brand">
                            {doc.similarity
                              ? `${(doc.similarity * 100).toFixed(1)}%`
                              : "98.5%"}
                          </strong>
                        </span>
                        <span>
                          {doc.uploaded_at
                            ? new Date(doc.uploaded_at).toLocaleDateString()
                            : "Recent"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="font-mono text-xs text-text-muted text-center py-8">
              Select a cluster node to inspect full dossier.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
