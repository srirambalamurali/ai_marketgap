import { create } from "zustand";

type DashboardState = {
  refreshKey: number;
  setRefreshKey: () => void;
  selectedReportId: string | null;
  setSelectedReportId: (value: string | null) => void;
};

export const useDashboardStore = create<DashboardState>((set) => ({
  refreshKey: 0,
  setRefreshKey: () => set((state) => ({ refreshKey: state.refreshKey + 1 })),
  selectedReportId: null,
  setSelectedReportId: (value) => set({ selectedReportId: value }),
}));
