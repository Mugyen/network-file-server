import { createContext, useContext } from "react";
import type { ReactElement, ReactNode } from "react";
import { useToast } from "../hooks/useToast.ts";
import ToastContainer from "../components/ToastContainer.tsx";

/** Full toast API exposed to consumers — same shape as the useToast result. */
type NotificationsContextValue = ReturnType<typeof useToast>;

const NotificationsContext = createContext<NotificationsContextValue | null>(
  null,
);

interface NotificationsProviderProps {
  children: ReactNode;
}

/**
 * Owns toast state and renders the ToastContainer overlay after its
 * children, so consumers only ever dispatch/dismiss notifications.
 */
export function NotificationsProvider({
  children,
}: NotificationsProviderProps): ReactElement {
  const toast = useToast();

  return (
    <NotificationsContext.Provider value={toast}>
      {children}
      <ToastContainer
        toasts={toast.visibleToasts}
        overflowCount={toast.overflowCount}
        onDismiss={toast.dismissToast}
      />
    </NotificationsContext.Provider>
  );
}

/**
 * Consumer hook for the notifications slice.
 * Throws if called outside a NotificationsProvider (strict contract).
 */
// eslint-disable-next-line react-refresh/only-export-components -- provider and its consumer hook are intentionally co-located; fast refresh falls back to a full reload here.
export function useNotifications(): NotificationsContextValue {
  const value = useContext(NotificationsContext);
  if (value === null) {
    throw new Error(
      "useNotifications must be used within a NotificationsProvider",
    );
  }
  return value;
}
