import { create } from "zustand";

type WorkflowState = {
  selectedQuery: string;
  setSelectedQuery: (value: string) => void;
};

export const useWorkflowStore = create<WorkflowState>((set) => ({
  selectedQuery: "AI startup productivity gaps",
  setSelectedQuery: (value) => set({ selectedQuery: value }),
}));
