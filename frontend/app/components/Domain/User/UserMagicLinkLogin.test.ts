import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import UserMagicLinkLogin from "./UserMagicLinkLogin.vue";

const post = vi.fn();
const signIn = vi.fn();
let wrapper: VueWrapper;

function render() {
  wrapper = mount(UserMagicLinkLogin, {
    props: { allowPassword: true },
    global: {
      mocks: { $globals: { icons: { email: "email" } } },
      stubs: {
        VForm: { template: "<form><slot /></form>" },
        VTextField: {
          props: ["modelValue", "errorMessages"],
          template: "<div><input :value=\"modelValue\" @input=\"$emit('update:modelValue', $event.target.value)\"><span>{{ errorMessages }}</span></div>",
        },
        VProgressCircular: { template: "<div />" },
        VBtn: { template: "<button><slot /></button>" },
        VAlert: { template: "<div><slot /></div>" },
      },
    },
  });
  return wrapper;
}

describe("magic-link login", () => {
  beforeEach(() => {
    post.mockReset();
    signIn.mockReset();
    vi.stubGlobal("useNuxtApp", () => ({ $axios: { post } }));
    vi.stubGlobal("useMealieAuth", () => ({ magicLinkSignIn: signIn }));
    window.history.replaceState({}, "", "/login");
  });

  afterEach(() => {
    wrapper?.unmount();
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  test("opening a link clears its fragment and immediately starts a remembered sign-in", async () => {
    const token = "a".repeat(43);
    signIn.mockImplementation(() => new Promise(() => {}));
    window.history.replaceState({}, "", `/login#magic=${token}`);
    render();
    await flushPromises();
    expect(window.location.hash).toBe("");
    expect(post).not.toHaveBeenCalled();
    expect(signIn).toHaveBeenCalledWith(token, true);
    expect(signIn).toHaveBeenCalledTimes(1);
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.find("[role=\"status\"]").exists()).toBe(true);
  });

  test("an invalid or used link lets the user request another", async () => {
    window.history.replaceState({}, "", `/login#magic=${"b".repeat(43)}`);
    signIn.mockRejectedValue(new Error("expired"));
    render();
    await flushPromises();
    expect(wrapper.find("input").exists()).toBe(true);
    expect(wrapper.find("[role=\"alert\"]").exists()).toBe(true);
  });

  test("a malformed link is cleared without attempting to authenticate", async () => {
    window.history.replaceState({}, "", "/login#magic=invalid");
    render();
    await flushPromises();
    expect(window.location.hash).toBe("");
    expect(signIn).not.toHaveBeenCalled();
    expect(wrapper.find("input").exists()).toBe(true);
    expect(wrapper.find("[role=\"alert\"]").exists()).toBe(true);
  });

  test("invalid email stays in the form without issuing a request", async () => {
    render();
    await wrapper.get("input").setValue("not-an-email");
    await wrapper.get("form").trigger("submit");
    expect(post).not.toHaveBeenCalled();
  });

  test("a successful request presents the generic check-email state", async () => {
    post.mockResolvedValue({ status: 202 });
    render();
    await wrapper.get("input").setValue("user@example.com");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/api/auth/magic-link", { email: "user@example.com" });
    expect(wrapper.find("[role=\"status\"]").exists()).toBe(true);
    expect(wrapper.find("input").exists()).toBe(false);
  });
});
