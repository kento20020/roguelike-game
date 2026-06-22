import { useEffect } from "react";
import { useGameStore } from "./store/gameStore";
import ErrorToast from "./components/common/ErrorToast";
import StartPage from "./pages/StartPage";
import ExploringPage from "./pages/ExploringPage";
import BattlePage from "./pages/BattlePage";
import TreasurePage from "./pages/TreasurePage";
import HealPage from "./pages/HealPage";
import GatePage from "./pages/GatePage";
import NextFloorPage from "./pages/NextFloorPage";
import ClearedPage from "./pages/ClearedPage";
import DeadPage from "./pages/DeadPage";

// phase → Page 切り替え（GDD §6 状態遷移 / §24.6 Pages）。
export default function App() {
  const state = useGameStore((s) => s.state);
  const error = useGameStore((s) => s.error);
  const clearError = useGameStore((s) => s.clearError);
  const loadCatalog = useGameStore((s) => s.loadCatalog);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  function page() {
    if (!state) return <StartPage />;
    switch (state.phase) {
      case "exploring":
        return <ExploringPage state={state} />;
      case "battle":
        return <BattlePage state={state} />;
      case "treasure_preview":
      case "treasure_opened":
        return <TreasurePage state={state} />;
      case "heal":
        return <HealPage state={state} />;
      case "gate_preview":
        return <GatePage state={state} />;
      case "gate_resolve":
      case "next_floor":
        return <NextFloorPage state={state} />;
      case "cleared":
        return <ClearedPage state={state} />;
      case "dead":
        return <DeadPage state={state} />;
      default:
        return <StartPage />;
    }
  }

  return (
    <>
      {page()}
      <ErrorToast error={error} onClose={clearError} />
    </>
  );
}
