"use client";

import React from "react";
import { HeaderBar } from "../../../components/HeaderBar";
import { FraudGraph } from "../../../components/command/FraudGraph";

export default function FraudClustersPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <HeaderBar
        title="FRAUD CLUSTER NETWORK"
        subtitle="MULTI-IDENTITY ANOMALY DETECTOR"
      />

      <main className="flex-1 p-4 sm:p-6 max-w-[1600px] w-full mx-auto">
        <FraudGraph />
      </main>
    </div>
  );
}
