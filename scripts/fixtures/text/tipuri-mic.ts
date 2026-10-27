// A small file written by hand for the offline tests of inventory_typescript.py. It has the constructs of a file of type declarations
// (the documents of a search index and the filters of a query). The words interface and type in this comment are not declarations: {
import type { ES_INDEX_PUBLIC } from "./utils";

export type IndexName = typeof ES_INDEX_PUBLIC | "other";
export type Id = string | number;

/** The filters of a query. A comment above a declaration belongs to the declaration, not to its first member. */
export interface Filters {
  db?: IndexName[];
  /** First day of the period, ISO 8601. */
  dateFrom?: string;
  // Lowest value,
  // in lei.
  valueFrom?: string;

  // This comment is cut off from the member below by a blank line.

  authority?: string; // the contracting authority
  cpv: string;
  readonly euFunds: boolean | null;
  "x-county": string;
  run(): void;
  go?(a: number): void;
  callback: (a: number, b: Map<string, number>) => void;
  kind:
    | "licitatii"
    | "achizitii"
    | "offline"; // the dataset
}

export interface Item extends Base, Mixin<Id> {
  id: number;
  name: string | null;
  supplier: {
    fiscalNumber: string;
    address: {
      county: string; // the county of the supplier
      city?: string;
    };
  };
  lots: {
    number: number;
    rows: { value: number }[];
  }[];
  winner: { id: number } | null;
  extra: Array<{ ignored: true }>;
  history: Record<string, { a: number }>;
}

export type Alias = {
  an: number;
  caen?: string;
};

export interface Empty extends Item {}

declare interface Declared {
  flag: boolean;
}

export const LIMITS = { interface: 1, type: 2 };
export function build(): { code: string } {
  const text = "interface NotADeclaration { a: string }";
  const other = `type Nope = { b: number } ${text}`;
  return { code: other };
}
export enum Kind {
  A = "a",
}
