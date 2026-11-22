import React, { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, SystemOverview, SystemHealth, TokenDetail } from "./api/client";
import { Navbar } from "./components/Navbar";
import { ConfirmationModal } from "./components/ConfirmationModal";
import { OverviewView } from "./views/OverviewView";
import { DiscoveryView } from "./views/DiscoveryView";
import { AgentsView } from "./views/AgentsView";
import { DecisionsView } from "./views/DecisionsView";
import { TradingView } from "./views/TradingView";
import { ResearchView } from "./views/ResearchView";
import { ControlCentreView } from "./views/ControlCentreView";
import { TokenDetailModal } from "./views/TokenDetailModal";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 10000,
      staleTime: 5000,
      retry: 2,
    },
  },
});

const DashboardContent: React.FC = () => {
  const qc = useQueryClient();
  const [currentTab, setCurrentTab] = useState<string>("overview");
  const [selectedMint, setSelectedMint] = useState<string | null>(null);
  const [tokenModalOpen, setTokenModalOpen] = useState<boolean>(false);

  // Position Close Confirmation state
  const [closePosModal, setClosePosModal] = useState<{
    isOpen: boolean;
    positionId: string;
  }>({
    isOpen: false,
    positionId: "",
  });

  // Queries
  const { data: overview, isLoading: overviewLoading } = useQuery<SystemOverview>({
    queryKey: ["overview"],
    queryFn: () => apiClient.getOverview(),
  });

  const { data: discoveryTokens = [], isLoading: discoveryLoading, refetch: refetchDiscovery } = useQuery({
    queryKey: ["discovery"],
    queryFn: () => apiClient.getDiscoveryTokens({ limit: 100 }),
  });

  const { data: investigations = [], isLoading: agentsLoading, refetch: refetchAgents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiClient.getAgentInvestigations({ limit: 50 }),
  });

  const { data: decisions = [], isLoading: decisionsLoading, refetch: refetchDecisions } = useQuery({
    queryKey: ["decisions"],
    queryFn: () => apiClient.getDecisions({ limit: 50 }),
  });

  const { data: positions = [], isLoading: positionsLoading, refetch: refetchPositions } = useQuery({
    queryKey: ["positions"],
    queryFn: () => apiClient.getPaperPositions(),
  });

  const { data: proposals = [], refetch: refetchProposals } = useQuery({
    queryKey: ["proposals"],
    queryFn: () => apiClient.getPaperProposals(),
  });

  const { data: performance, isLoading: researchLoading, refetch: refetchResearch } = useQuery({
    queryKey: ["research"],
    queryFn: () => apiClient.getResearchPerformance(),
  });

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery<SystemHealth>({
    queryKey: ["health"],
    queryFn: () => apiClient.getSystemHealth(),
  });

  const { data: tokenDetail } = useQuery<TokenDetail>({
    queryKey: ["token", selectedMint],
    queryFn: () => apiClient.getTokenDetail(selectedMint!),
    enabled: !!selectedMint && tokenModalOpen,
  });

  // SSE Real-time Telemetry Subscription
  useEffect(() => {
    let es: EventSource | null = null;
    try {
      es = apiClient.createTelemetryStream((event: any) => {
        if (event.event_type === "heartbeat") {
          qc.invalidateQueries({ queryKey: ["overview"] });
        } else if (event.event_type === "discovery") {
          qc.invalidateQueries({ queryKey: ["discovery"] });
          qc.invalidateQueries({ queryKey: ["overview"] });
        } else if (event.event_type === "decision") {
          qc.invalidateQueries({ queryKey: ["decisions"] });
        } else if (event.event_type === "paper_order" || event.event_type === "position_update") {
          qc.invalidateQueries({ queryKey: ["positions"] });
          qc.invalidateQueries({ queryKey: ["overview"] });
        } else if (event.event_type === "investigation_completed") {
          qc.invalidateQueries({ queryKey: ["agents"] });
        }
      });
    } catch {
      // SSE fallback
    }

    return () => {
      if (es) es.close();
    };
  }, [qc]);

  const handleSelectToken = (mint: string) => {
    setSelectedMint(mint);
    setTokenModalOpen(true);
  };

  const handleTriggerInvestigation = async (mint: string) => {
    try {
      await apiClient.triggerInvestigation(mint);
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["token", mint] });
    } catch (err) {
      console.error("Failed to trigger investigation:", err);
    }
  };

  const handleExecuteControl = async (cmd: {
    action: string;
    confirmation?: boolean;
    target_id?: string;
    parameters?: any;
    operator_notes?: string;
  }) => {
    const res = await apiClient.executeControl(cmd);
    qc.invalidateQueries({ queryKey: ["health"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
    qc.invalidateQueries({ queryKey: ["positions"] });
    return res;
  };

  const handlePromptClosePosition = (positionId: string) => {
    setClosePosModal({
      isOpen: true,
      positionId,
    });
  };

  const handleConfirmClosePosition = async () => {
    if (!closePosModal.positionId) return;
    try {
      await apiClient.executeControl({
        action: "close_position",
        confirmation: true,
        target_id: closePosModal.positionId,
        operator_notes: "Manual liquidation via Paper Trading Center",
      });
      setClosePosModal({ isOpen: false, positionId: "" });
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      console.error("Failed to close position:", err);
    }
  };

  const systemStatus = health?.overall_status || (overview ? "operational" : "initializing");
  const emergencyStop = health?.emergency_stop_engaged ?? false;
  const portfolioEquity = overview?.portfolio_net_equity ?? 10000;

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col font-sans selection:bg-primary/30 selection:text-primary">
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        systemStatus={systemStatus}
        emergencyStop={emergencyStop}
        portfolioEquity={portfolioEquity}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentTab === "overview" && (
          <OverviewView
            overview={overview}
            isLoading={overviewLoading}
            onNavigate={(tab) => setCurrentTab(tab)}
          />
        )}

        {currentTab === "discovery" && (
          <DiscoveryView
            tokens={discoveryTokens}
            isLoading={discoveryLoading}
            onSelectToken={handleSelectToken}
            onRefresh={() => refetchDiscovery()}
          />
        )}

        {currentTab === "agents" && (
          <AgentsView
            investigations={investigations}
            isLoading={agentsLoading}
            onRefresh={() => refetchAgents()}
            onSelectToken={handleSelectToken}
          />
        )}

        {currentTab === "decisions" && (
          <DecisionsView
            decisions={decisions}
            isLoading={decisionsLoading}
            onRefresh={() => refetchDecisions()}
            onSelectToken={handleSelectToken}
          />
        )}

        {currentTab === "trading" && (
          <TradingView
            positions={positions}
            proposals={proposals}
            isLoading={positionsLoading}
            onRefresh={() => {
              refetchPositions();
              refetchProposals();
            }}
            onClosePosition={handlePromptClosePosition}
            onSelectToken={handleSelectToken}
          />
        )}

        {currentTab === "research" && (
          <ResearchView
            performance={performance}
            isLoading={researchLoading}
            onRefresh={() => refetchResearch()}
          />
        )}

        {currentTab === "controls" && (
          <ControlCentreView
            health={health}
            isLoading={healthLoading}
            onRefresh={() => refetchHealth()}
            onExecuteControl={handleExecuteControl}
          />
        )}
      </main>

      {/* Token Detail Modal */}
      <TokenDetailModal
        token={tokenDetail || null}
        isOpen={tokenModalOpen}
        onClose={() => {
          setTokenModalOpen(false);
          setSelectedMint(null);
        }}
        onTriggerInvestigation={handleTriggerInvestigation}
      />

      {/* Manual Position Close Confirmation Modal */}
      <ConfirmationModal
        isOpen={closePosModal.isOpen}
        title="Confirm Simulated Position Exit"
        description={`Are you sure you want to manually exit simulated paper position ${closePosModal.positionId}? A paper market order will be simulated immediately at the current pool mark price with modeled slippage and priority fees.`}
        confirmText="Exit Position Now"
        variant="danger"
        onConfirm={handleConfirmClosePosition}
        onCancel={() => setClosePosModal({ isOpen: false, positionId: "" })}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  );
};

export default App;
