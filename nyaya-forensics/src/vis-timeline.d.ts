// Minimal ambient types for vis-timeline / vis-data (we use DataSet + Timeline).
// Keeps the build independent of @types/vis-timeline resolution quirks.
declare module "vis-timeline" {
  export class Timeline {
    constructor(container: HTMLElement, items: any, options?: any);
    setItems(items: any): void;
    setOptions(options: any): void;
    destroy(): void;
  }
}
declare module "vis-data" {
  export class DataSet {
    constructor(data?: any[]);
    add(data: any | any[]): void;
    clear(): void;
    get(): any[];
  }
}