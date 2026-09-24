import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkflowRunType } from '@/lib/generated-api';
import { applyPreset, presetIsActive, WorkflowPresetChips } from './workflow-presets';

const { ActiveVoice, AdvocacyToneV2, ReferenceValidationV2, RecommendationCheck, ConcisionPrecision } = WorkflowRunType;

const EDITORIAL = [AdvocacyToneV2, ActiveVoice, ConcisionPrecision];
const OFFERED = [ReferenceValidationV2, RecommendationCheck, AdvocacyToneV2, ActiveVoice, ConcisionPrecision];

describe('presetIsActive', () => {
  it('is active when the selection is exactly the preset', () => {
    expect(presetIsActive(EDITORIAL, [ActiveVoice, ConcisionPrecision, AdvocacyToneV2], OFFERED)).toBe(true);
  });

  it('is not active for a subset or a superset of the preset', () => {
    expect(presetIsActive(EDITORIAL, [ActiveVoice, AdvocacyToneV2], OFFERED)).toBe(false);
    expect(presetIsActive(EDITORIAL, [...EDITORIAL, ReferenceValidationV2], OFFERED)).toBe(false);
  });

  it('ignores assessments the picker is not offering, on both sides', () => {
    // Concision is hidden for this user: the preset shrinks to what is on offer.
    const offered = [ReferenceValidationV2, AdvocacyToneV2, ActiveVoice];
    expect(presetIsActive(EDITORIAL, [ActiveVoice, AdvocacyToneV2], offered)).toBe(true);
    // A seeded type with no row neither confirms nor breaks the match.
    expect(presetIsActive(EDITORIAL, [ActiveVoice, AdvocacyToneV2, ConcisionPrecision], offered)).toBe(true);
  });

  it('is never active for a preset with nothing on offer', () => {
    expect(presetIsActive(EDITORIAL, [], [ReferenceValidationV2])).toBe(false);
  });
});

describe('applyPreset', () => {
  it('replaces the offered part of the selection with the preset', () => {
    expect(applyPreset(EDITORIAL, [ReferenceValidationV2, RecommendationCheck], OFFERED)).toEqual(EDITORIAL);
  });

  it('keeps a seeded type the picker does not list', () => {
    const offered = [ReferenceValidationV2, AdvocacyToneV2, ActiveVoice];
    expect(applyPreset(EDITORIAL, [ConcisionPrecision, ReferenceValidationV2], offered)).toEqual([
      ConcisionPrecision,
      AdvocacyToneV2,
      ActiveVoice,
    ]);
  });

  it('drops preset assessments that are not on offer', () => {
    expect(applyPreset(EDITORIAL, [], [AdvocacyToneV2])).toEqual([AdvocacyToneV2]);
  });
});

describe('WorkflowPresetChips', () => {
  const presets = [
    { slug: 'editorial_review', label: 'Editorial Review', description: 'Language checks.', workflows: EDITORIAL },
    {
      slug: 'standard_review',
      label: 'Standard Review',
      description: 'The usual.',
      workflows: [ReferenceValidationV2, AdvocacyToneV2, RecommendationCheck],
    },
  ];

  function markup(selected: WorkflowRunType[]): string {
    return renderToStaticMarkup(
      <WorkflowPresetChips
        presets={presets}
        selectedTypes={selected}
        offeredTypes={OFFERED}
        onSelectionChange={() => undefined}
        getWorkflowTypeName={(type) => type}
      />,
    );
  }

  it('presses the chip whose set the selection is, and no other', () => {
    const chips = markup(EDITORIAL).split('<button').slice(1);
    expect(chips).toHaveLength(2);
    expect(chips[0]).toContain('aria-pressed="true"');
    expect(chips[0]).toContain('Editorial Review');
    expect(chips[1]).toContain('aria-pressed="false"');
  });

  it('shows how many offered assessments each preset selects', () => {
    const [editorial, standard] = markup([]).split('<button').slice(1);
    expect(editorial).toMatch(/>3<\/span>/);
    expect(standard).toMatch(/>3<\/span>/);
  });
});
