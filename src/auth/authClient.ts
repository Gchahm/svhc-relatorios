import { cloudflareClient } from "better-auth-cloudflare/client";
import { createAuthClient } from "better-auth/react";

const client = createAuthClient({
    plugins: [cloudflareClient()],
});

export default client;
