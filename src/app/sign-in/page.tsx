"use client";

import authClient from "@/auth/authClient";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTranslation } from "@/lib/i18n/client";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function SignInPage() {
    const t = useTranslation();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    useEffect(() => {
        document.title = t("app.title");
    }, [t]);

    const handleSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);
        try {
            const result = await authClient.signIn.email({ email, password });
            if (result.error) {
                // Map the known better-auth code to a catalog message so the error renders
                // in the active locale (better-auth's own message is English-only).
                const code = result.error.code;
                if (code === "INVALID_EMAIL_OR_PASSWORD") {
                    setError(t("auth.invalid_credentials"));
                } else {
                    setError(t("auth.sign_in_error"));
                }
            } else {
                window.location.href = "/dashboard";
            }
        } catch {
            setError(t("auth.unexpected_error"));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen p-8 font-[family-name:var(--font-geist-sans)]">
            <Card className="w-full max-w-sm">
                <CardHeader>
                    <CardTitle className="text-2xl">{t("auth.sign_in_title")}</CardTitle>
                    <CardDescription>{t("auth.sign_in_description")}</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSignIn} className="grid gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="email">{t("auth.email_label")}</Label>
                            <Input
                                id="email"
                                type="email"
                                placeholder={t("auth.sign_in_email_placeholder")}
                                required
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="password">{t("auth.password_label")}</Label>
                            <Input
                                id="password"
                                type="password"
                                required
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={isLoading}>
                            {isLoading ? t("auth.signing_in") : t("auth.sign_in_button")}
                        </Button>
                    </form>

                    {error && <p className="text-destructive text-sm text-center mt-4">{error}</p>}

                    <p className="text-sm text-center mt-4 text-muted-foreground">
                        {t("auth.no_account_prompt")}{" "}
                        <Link href="/sign-up" className="text-primary underline underline-offset-4">
                            {t("auth.create_account_link")}
                        </Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
