"use client";

import authClient from "@/auth/authClient";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/lib/i18n/client";
import { LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

interface UserMenuProps {
    name: string;
    email: string;
}

export default function UserMenu({ name, email }: UserMenuProps) {
    const t = useTranslation();
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    const [, startTransition] = useTransition();

    const handleSignOut = async () => {
        setIsLoading(true);
        try {
            await authClient.signOut({
                fetchOptions: {
                    onSuccess: () => {
                        startTransition(() => {
                            router.replace("/");
                        });
                    },
                },
            });
        } catch (e) {
            console.error("Sign out error:", e);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-1.5 text-sm text-gray-600 h-8">
                    <User className="h-3.5 w-3.5" />
                    {name}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuLabel className="font-normal">
                    <p className="text-sm font-medium">{name}</p>
                    <p className="text-xs text-muted-foreground truncate">{email}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleSignOut} disabled={isLoading} className="text-red-600 cursor-pointer">
                    <LogOut className="h-3.5 w-3.5 mr-2" />
                    {isLoading ? t("auth.signing_out") : t("auth.sign_out")}
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
