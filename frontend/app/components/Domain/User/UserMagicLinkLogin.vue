<template>
  <div>
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
      role="alert"
    >
      {{ error }}
    </v-alert>

    <div v-if="token" role="status" aria-live="polite" class="text-center py-4">
      <v-progress-circular indeterminate color="primary" aria-hidden="true" />
      <p class="mt-3">
        {{ $t('magic-link.signing-in') }}
      </p>
    </div>

    <template v-else-if="sent">
      <div role="status" aria-live="polite">
        <h2 class="text-h6 mb-2">
          {{ $t('magic-link.check-email') }}
        </h2>
        <p class="mb-2">
          {{ $t('magic-link.sent-description') }}
        </p>
        <p class="text-body-2 mb-4">
          {{ $t('magic-link.delivery-help') }}
        </p>
      </div>
      <v-btn variant="text" block @click="sent = false">
        {{ $t('magic-link.try-again') }}
      </v-btn>
    </template>

    <v-form v-else @submit.prevent="requestLink">
      <p class="mb-4">
        {{ $t('magic-link.description') }}
      </p>
      <v-text-field
        v-model="email"
        :label="$t('user.email')"
        :prepend-inner-icon="$globals.icons.email"
        variant="solo-filled"
        flat
        type="email"
        name="email"
        autocomplete="email"
        maxlength="254"
        required
        :disabled="busy"
        :error-messages="emailError"
        @update:model-value="emailError = ''"
      />
      <v-btn type="submit" color="primary" size="large" block :loading="busy">
        {{ $t('magic-link.send') }}
      </v-btn>
    </v-form>

    <v-btn
      v-if="allowPassword"
      variant="text"
      block
      class="mt-3"
      :disabled="busy"
      @click="$emit('use-password')"
    >
      {{ $t('magic-link.use-password') }}
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import type { MagicLinkRequest } from "~/lib/api/types/user";

defineProps<{ allowPassword: boolean }>();
defineEmits<{ "use-password": [] }>();

const { $axios } = useNuxtApp();
const auth = useMealieAuth();
const i18n = useI18n();
const email = ref("");
const token = ref("");
const busy = ref(false);
const sent = ref(false);
const error = ref("");
const emailError = ref("");

onMounted(async () => {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const candidate = fragment.get("magic");
  if (candidate !== null) {
    // Clear the credential from the URL before exchanging it for a session.
    window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    if (/^[A-Za-z0-9_-]{43}$/.test(candidate)) {
      token.value = candidate;
      await verifyLink();
    }
    else {
      error.value = i18n.t("magic-link.invalid");
    }
  }
});

async function requestLink() {
  if (busy.value) return;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    emailError.value = i18n.t("magic-link.email-required");
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const body: MagicLinkRequest = { email: email.value.trim() };
    await $axios.post("/api/auth/magic-link", body);
    sent.value = true;
  }
  catch {
    error.value = i18n.t("magic-link.request-error");
  }
  finally {
    busy.value = false;
  }
}

async function verifyLink() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await auth.magicLinkSignIn(token.value, true);
    token.value = "";
  }
  catch {
    token.value = "";
    error.value = i18n.t("magic-link.invalid");
  }
  finally {
    busy.value = false;
  }
}
</script>
