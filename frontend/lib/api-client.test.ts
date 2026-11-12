import { describe, expect, it } from 'vitest';
import { client } from '@/lib/generated-api/client.gen';
import { ApiError } from './api-error';
import './api-client';

function failWith(status: number, body: unknown) {
  const fetch = async () =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  return client.get({ url: '/anything', fetch }).then(
    () => undefined,
    (error: unknown) => error,
  );
}

describe('API client error mapping', () => {
  it('keeps a string detail as the ApiError reason', async () => {
    const error = await failWith(409, { detail: 'Project is busy' });

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, detail: 'Project is busy', message: 'Project is busy' });
  });

  it('drops a validation 422 detail list instead of storing it as the reason', async () => {
    const error = await failWith(422, {
      detail: [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }],
    });

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, detail: undefined, message: 'HTTP 422' });
  });
});
