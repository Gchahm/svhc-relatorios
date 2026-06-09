import type { D1Database, KVNamespace, R2Bucket } from "@cloudflare/workers-types";

declare global {
    interface CloudflareEnv {
        DATABASE: D1Database;
        KV: KVNamespace<string>;
        DOCUMENTS: R2Bucket;
        BETTER_AUTH_SECRET: string;
        BETTER_AUTH_URL: string;
        BETTER_AUTH_TRUSTED_ORIGINS: string;
    }
}

export {};
