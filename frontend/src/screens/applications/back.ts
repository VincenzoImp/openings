// The list an application page returns to: the address of Applications as
// the person last filtered it in this tab.
let last = "#applications";

export function rememberList(hash: string) {
  last = hash || "#applications";
}

export const listHref = () => last;
