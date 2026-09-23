import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { StepIndicator } from './step-indicator';

const STEPS = [
  { label: 'Your Document', completed: true },
  { label: 'Choose Assessments', completed: false },
];

describe('StepIndicator', () => {
  it('marks the current step for assistive technology', () => {
    const html = renderToStaticMarkup(<StepIndicator currentStep={2} steps={STEPS} />);
    const items = html.split('<li').slice(1);
    expect(items).toHaveLength(2);
    expect(items[0]).not.toContain('aria-current="step"');
    expect(items[1]).toContain('aria-current="step"');
  });

  it('draws a check for a completed step and the number for the rest', () => {
    const html = renderToStaticMarkup(<StepIndicator currentStep={2} steps={STEPS} />);
    const [first, second] = html.split('<li').slice(1);
    expect(first).toContain('lucide-check');
    expect(second).not.toContain('lucide-check');
    expect(second).toContain('>2<');
  });

  it('keeps only the current label on narrow screens', () => {
    const html = renderToStaticMarkup(<StepIndicator currentStep={2} steps={STEPS} />);
    const [first, second] = html.split('<li').slice(1);
    expect(first).toMatch(/hidden[^"]*sm:inline[^"]*">Your Document</);
    expect(second).not.toMatch(/hidden[^"]*">Choose Assessments</);
  });
});
