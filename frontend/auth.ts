import NextAuth, { DefaultSession } from 'next-auth';
import Google from 'next-auth/providers/google';
import MicrosoftEntraID from 'next-auth/providers/microsoft-entra-id';
import { JWTPayload, SignJWT } from 'jose';

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
    jwt: ({ token, account, user, profile }) => {
      // Add the access token to the token object so it can be used in the session
      if (account) {
        token.uid = `${account.provider}:${account.providerAccountId}`;
        token.email = user?.email ?? profile?.email;
        token.name = user?.name ?? profile?.name;
        token.provider = account.provider;
      }
      return token;
    },
    session: async ({ session, token }) => {
      const payload: JWTPayload = {
        sub: token.uid as string,
        email: token.email,
        name: token.name,
        provider: token.provider,
        iss: 'ai-reviewer',
        aud: 'ai-reviewer-api',
      };
      const accessToken = await new SignJWT(payload)
        .setProtectedHeader({
          alg: 'HS512',
          typ: 'JWT',
        })
        .setIssuedAt()
        .setExpirationTime('15m')
        .sign(new TextEncoder().encode(process.env.AUTH_SECRET!));

      return { ...session, accessToken };
    },
  },
});

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
    user: {} & DefaultSession['user'];
  }
}
