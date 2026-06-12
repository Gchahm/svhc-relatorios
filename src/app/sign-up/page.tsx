"use client";

import authClient from "@/auth/authClient";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTranslation } from "@/lib/i18n/client";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function SignUpPage() {
    const t = useTranslation();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    useEffect(() => {
        document.title = t("app.title");
    }, [t]);

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (password !== confirmPassword) {
            setError(t("auth.passwords_no_match"));
            return;
        }

        setIsLoading(true);
        try {
            const result = await authClient.signUp.email({ name, email, password });
            if (result.error) {
                // Map known better-auth codes to catalog messages so errors render in the
                // active locale (better-auth's own messages are English-only).
                const code = result.error.code;
                if (code === "USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL") {
                    setError(t("auth.email_in_use"));
                } else {
                    setError(t("auth.sign_up_error"));
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
                    <CardTitle className="text-2xl">{t("auth.sign_up_title")}</CardTitle>
                    <CardDescription>{t("auth.sign_up_description")}</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSignUp} className="grid gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="name">{t("auth.name_label")}</Label>
                            <Input
                                id="name"
                                type="text"
                                placeholder={t("auth.name_placeholder")}
                                required
                                value={name}
                                onChange={e => setName(e.target.value)}
                            />
                        </div>
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
                                minLength={8}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="confirm-password">{t("auth.confirm_password_label")}</Label>
                            <Input
                                id="confirm-password"
                                type="password"
                                required
                                minLength={8}
                                value={confirmPassword}
                                onChange={e => setConfirmPassword(e.target.value)}
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={isLoading}>
                            {isLoading ? t("auth.signing_up") : t("auth.sign_up_button")}
                        </Button>
                    </form>

                    {error && <p className="text-destructive text-sm text-center mt-4">{error}</p>}

                    <p className="text-sm text-center mt-4 text-muted-foreground">
                        {t("auth.have_account_prompt")}{" "}
                        <Link href="/sign-in" className="text-primary underline underline-offset-4">
                            {t("auth.sign_in_link")}
                        </Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
