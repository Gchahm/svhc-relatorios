/**
 * I18N Message Catalog
 * Typed, nested dictionary with pt-BR as canonical locale and en as optional fallback.
 * Missing en keys automatically fall back to pt-BR at runtime.
 */

export type SupportedLocale = "pt-BR" | "en";

/**
 * Define the complete catalog shape for type safety.
 * All keys in pt-BR must be present here.
 */
export type CatalogShape = {
    nav: {
        home: string;
        entries: string;
        documents: string;
        alerts: string;
        dashboard: string;
        settings: string;
    };
    button: {
        submit: string;
        cancel: string;
        save: string;
        delete: string;
        close: string;
        search: string;
        download: string;
        upload: string;
    };
    page: {
        entries_title: string;
        entries_description: string;
        documents_title: string;
        documents_description: string;
        alerts_title: string;
        alerts_description: string;
    };
    dialog: {
        attachment_detail_title: string;
        confirm_delete_title: string;
        confirm_delete_message: string;
        attachment_analysis_detail: string;
    };
    table: {
        period: string;
        date: string;
        amount: string;
        vendor: string;
        description: string;
        attachment: string;
        actions: string;
        status: string;
        type: string;
    };
    form: {
        search_placeholder: string;
        select_period: string;
        select_placeholder: string;
        no_results: string;
        loading: string;
    };
    badge: {
        pending: string;
        classified: string;
        analyzed: string;
        error: string;
        success: string;
        warning: string;
        info: string;
    };
    alert: {
        types: {
            attachment_amount_mismatch: string;
            attachment_vendor_mismatch: string;
            attachment_date_mismatch: string;
            attachment_page_error: string;
            duplicate_billing: string;
            duplicate_entry: string;
            negative_credit: string;
            large_expense_no_attachment: string;
            document_overpayment: string;
            scrape_inconsistency: string;
            portal_row_vanished: string;
        };
    };
    error: {
        not_found: string;
        unauthorized: string;
        server_error: string;
        network_error: string;
        loading_failed: string;
    };
    common: {
        loading: string;
        no_data: string;
        error: string;
        success: string;
        confirm: string;
        yes: string;
        no: string;
    };
    auth: {
        sign_in_title: string;
        sign_in_description: string;
        email_label: string;
        password_label: string;
        sign_in_button: string;
        sign_in_error: string;
        invalid_credentials: string;
        session_expired: string;
        sign_out: string;
    };
    formatting: {
        currency: string;
        date: string;
        percent: string;
    };
};

/**
 * Complete message catalog
 * pt-BR: canonical, complete translations
 * en: optional, partial translations (fallback to pt-BR)
 */
export const catalog: Record<SupportedLocale, CatalogShape> = {
    "pt-BR": {
        nav: {
            home: "Início",
            entries: "Lançamentos",
            documents: "Documentos",
            alerts: "Alertas",
            dashboard: "Dashboard",
            settings: "Configurações",
        },
        button: {
            submit: "Enviar",
            cancel: "Cancelar",
            save: "Salvar",
            delete: "Deletar",
            close: "Fechar",
            search: "Pesquisar",
            download: "Baixar",
            upload: "Enviar",
        },
        page: {
            entries_title: "Lançamentos",
            entries_description: "Visualize e analise os lançamentos do condomínio",
            documents_title: "Documentos",
            documents_description: "Documentos fiscais identificados e analisados",
            alerts_title: "Alertas",
            alerts_description: "Divergências e achados da auditoria",
        },
        dialog: {
            attachment_detail_title: "Detalhes do Documento",
            confirm_delete_title: "Confirmar Exclusão",
            confirm_delete_message: "Tem certeza que deseja excluir este item?",
            attachment_analysis_detail: "Análise do Documento",
        },
        table: {
            period: "Período",
            date: "Data",
            amount: "Valor",
            vendor: "Fornecedor",
            description: "Descrição",
            attachment: "Documento",
            actions: "Ações",
            status: "Status",
            type: "Tipo",
        },
        form: {
            search_placeholder: "Pesquisar por descrição...",
            select_period: "Selecione um período",
            select_placeholder: "Selecionar...",
            no_results: "Nenhum resultado encontrado",
            loading: "Carregando...",
        },
        badge: {
            pending: "Pendente",
            classified: "Classificado",
            analyzed: "Analisado",
            error: "Erro",
            success: "Sucesso",
            warning: "Aviso",
            info: "Informação",
        },
        alert: {
            types: {
                attachment_amount_mismatch: "Divergência de Valor",
                attachment_vendor_mismatch: "Divergência de Fornecedor",
                attachment_date_mismatch: "Divergência de Data",
                attachment_page_error: "Erro na Página",
                duplicate_billing: "Cobrança Duplicada",
                duplicate_entry: "Lançamento Duplicado",
                negative_credit: "Crédito Negativo",
                large_expense_no_attachment: "Grande Despesa sem Documento",
                document_overpayment: "Pagamento Excessivo do Documento",
                scrape_inconsistency: "Inconsistência nos Dados",
                portal_row_vanished: "Linha Removida do Portal",
            },
        },
        error: {
            not_found: "Não encontrado",
            unauthorized: "Não autorizado",
            server_error: "Erro no servidor",
            network_error: "Erro de conexão",
            loading_failed: "Falha ao carregar",
        },
        common: {
            loading: "Carregando...",
            no_data: "Sem dados",
            error: "Erro",
            success: "Sucesso",
            confirm: "Confirmar",
            yes: "Sim",
            no: "Não",
        },
        auth: {
            sign_in_title: "Entrar",
            sign_in_description: "Acesse sua conta para continuar",
            email_label: "Email",
            password_label: "Senha",
            sign_in_button: "Entrar",
            sign_in_error: "Falha ao entrar",
            invalid_credentials: "Email ou senha inválidos",
            session_expired: "Sua sessão expirou",
            sign_out: "Sair",
        },
        formatting: {
            currency: "R$",
            date: "DD/MM/YYYY",
            percent: "%",
        },
    },
    en: {
        nav: {
            home: "Home",
            entries: "Entries",
            documents: "Documents",
            alerts: "Alerts",
            dashboard: "Dashboard",
            settings: "Settings",
        },
        button: {
            submit: "Submit",
            cancel: "Cancel",
            save: "Save",
            delete: "Delete",
            close: "Close",
            search: "Search",
            download: "Download",
            upload: "Upload",
        },
        page: {
            entries_title: "Entries",
            entries_description: "View and analyze condominium entries",
            documents_title: "Documents",
            documents_description: "Identified and analyzed fiscal documents",
            alerts_title: "Alerts",
            alerts_description: "Audit findings and discrepancies",
        },
        dialog: {
            attachment_detail_title: "Document Details",
            confirm_delete_title: "Confirm Deletion",
            confirm_delete_message: "Are you sure you want to delete this item?",
            attachment_analysis_detail: "Document Analysis",
        },
        table: {
            period: "Period",
            date: "Date",
            amount: "Amount",
            vendor: "Vendor",
            description: "Description",
            attachment: "Document",
            actions: "Actions",
            status: "Status",
            type: "Type",
        },
        form: {
            search_placeholder: "Search by description...",
            select_period: "Select a period",
            select_placeholder: "Select...",
            no_results: "No results found",
            loading: "Loading...",
        },
        badge: {
            pending: "Pending",
            classified: "Classified",
            analyzed: "Analyzed",
            error: "Error",
            success: "Success",
            warning: "Warning",
            info: "Info",
        },
        alert: {
            types: {
                attachment_amount_mismatch: "Amount Mismatch",
                attachment_vendor_mismatch: "Vendor Mismatch",
                attachment_date_mismatch: "Date Mismatch",
                attachment_page_error: "Page Error",
                duplicate_billing: "Duplicate Billing",
                duplicate_entry: "Duplicate Entry",
                negative_credit: "Negative Credit",
                large_expense_no_attachment: "Large Expense No Attachment",
                document_overpayment: "Document Overpayment",
                scrape_inconsistency: "Data Inconsistency",
                portal_row_vanished: "Row Removed from Portal",
            },
        },
        error: {
            not_found: "Not found",
            unauthorized: "Unauthorized",
            server_error: "Server error",
            network_error: "Network error",
            loading_failed: "Failed to load",
        },
        common: {
            loading: "Loading...",
            no_data: "No data",
            error: "Error",
            success: "Success",
            confirm: "Confirm",
            yes: "Yes",
            no: "No",
        },
        auth: {
            sign_in_title: "Sign In",
            sign_in_description: "Sign in to your account to continue",
            email_label: "Email",
            password_label: "Password",
            sign_in_button: "Sign In",
            sign_in_error: "Failed to sign in",
            invalid_credentials: "Invalid email or password",
            session_expired: "Your session has expired",
            sign_out: "Sign Out",
        },
        formatting: {
            currency: "USD",
            date: "MM/DD/YYYY",
            percent: "%",
        },
    },
};

/**
 * Type helper for catalog keys (enables type-safe key lookup)
 */
export type CatalogKey = keyof CatalogShape;

/**
 * Recursively extract all dot-notation leaf paths from a nested catalog shape,
 * including nested sections like `alert.types.*` (so every key is type-checked).
 */
type Paths<T> = {
    [K in keyof T & string]: T[K] extends string ? K : `${K}.${Paths<T[K]>}`;
}[keyof T & string];

/**
 * Extract all possible keys from the catalog shape recursively
 */
export type DeepCatalogKey = Paths<CatalogShape>;
