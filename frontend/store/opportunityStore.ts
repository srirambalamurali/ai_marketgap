import { create } from "zustand";

type OpportunityState = {
  query: string;
  setQuery: (value: string) => void;
  sort: "score" | "confidence" | "recent";
  setSort: (value: OpportunityState["sort"]) => void;
};

export const useOpportunityStore = create<OpportunityState>((set) => ({
  query: "",
  setQuery: (value) => set({ query: value }),
  sort: "score",
  setSort: (value) => set({ sort: value }),
}));
