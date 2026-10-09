import { JWTPayload, SignJWT } from 'jose';
import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import MicrosoftEntraID from 'next-auth/providers/microsoft-entra-id';

export const { handlers, signIn, signOut, auth } = NextAuth({
  theme: {
    colorScheme: 'light',
  },
  providers: [
    ...(process.env.AUTH_GOOGLE_ID
      ? [
          Google({
            clientId: process.env.AUTH_GOOGLE_ID,
            clientSecret: process.env.AUTH_GOOGLE_SECRET,
          }),
        ]
      : []),
    ...(process.env.AUTH_MICROSOFT_ENTRA_ID_ID
      ? [
          MicrosoftEntraID({
            clientId: process.env.AUTH_MICROSOFT_ENTRA_ID_ID,
            clientSecret: process.env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            issuer: process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
          }),
        ]
      : []),
  ],
  callbacks: {
    jwt: async ({ token, account, user, profile }) => {
      // Store basic identity info on initial sign-in
      if (account) {
        token.uid = `${account.provider}:${account.providerAccountId}`;
        token.email = user?.email ?? profile?.email;
        token.name = user?.name ?? profile?.name;
        token.provider = account.provider;
        // A Microsoft account is identified by its Entra object id in its tenant. The
        // Word add-in is released Teams handoffs by these, never by email.
        if (account.provider === 'microsoft-entra-id') {
          token.oid = profile?.oid;
          token.tid = profile?.tid;
        }
      }
      return token;
    },
    session: async ({ session, token }) => {
      const accessToken = await createAccessToken(token);

      return {
        ...session,
        accessToken,
      };
    },
  },
});

async function createAccessToken(token: Record<string, unknown>): Promise<string> {
  const payload: JWTPayload = {
    sub: token.uid as string,
    email: token.email as string,
    name: token.name as string,
    provider: token.provider as string,
    ...(token.oid ? { oid: token.oid as string, tid: token.tid as string | undefined } : {}),
    iss: 'ai-reviewer',
    aud: 'ai-reviewer-api',
  };
  return new SignJWT(payload)
    .setProtectedHeader({
      alg: 'HS512',
      typ: 'JWT',
    })
    .setIssuedAt()
    .setExpirationTime('15m')
    .sign(new TextEncoder().encode(process.env.AUTH_SECRET!));
}

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
  }
}
