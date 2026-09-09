import { create } from 'zustand';

interface AssessmentRailState {
  /**
   * Whether the "Pipeline steps" section is expanded. `null` until the reader
   * has toggled it, so the rail can fall back to whether the selected
   * assessment lives inside the section.
   */
  pipelineStepsOpen: boolean | null;
  setPipelineStepsOpen: (open: boolean) => void;
}

/**
 * Selecting an assessment changes the route, which remounts the rail. Anything
 * the reader has folded open lives here so it survives that remount.
 */
export const useAssessmentRailStore = create<AssessmentRailState>((set) => ({
  pipelineStepsOpen: null,
  setPipelineStepsOpen: (open) => set({ pipelineStepsOpen: open }),
}));
