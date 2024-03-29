<template>
  <p v-if="isLoading">
    Loading...
    <spinner />
  </p>

  <div v-else>
    <json-forms
      :data="formData"
      :schema="schema"
      :uischema="uischema"
      :renderers="renderers"
      @change="onChange"
    />

    <hr>

    <a-button type="primary" @click="onSubmit">
      Create EPS project and generate address file
    </a-button>
  </div>
</template>

<script setup="props">
import {defineProps, ref} from "vue";
import {useWorkflow} from "../../../../composables/workflow.js";
import {workflowGetJsonForm, workflowPostData} from "../../utils/api.js";

// eslint-disable-next-line no-unused-vars
import {defaultStyles, mergeStyles, vanillaRenderers,} from "@jsonforms/vue-vanilla";
import "@jsonforms/vue-vanilla/vanilla.css"; // eslint-disable-next-line no-unused-vars
import Swal from "sweetalert2"; // eslint-disable-next-line no-unused-vars
import {default as Spinner} from "../../../Spinner"; // eslint-disable-next-line no-unused-vars
import { JsonForms } from "@jsonforms/vue";
// eslint-disable-next-line no-unused-vars
const myStyles = mergeStyles(defaultStyles, { control: { label: "mylabel" } });
// eslint-disable-next-line no-unused-vars
const renderers = Object.freeze([...vanillaRenderers]);

const props = defineProps({
  workflowStep: {
    type: Object,
    default: null,
    required: true,
  },
});

const workflowStep = props.workflowStep;
// eslint-disable-next-line no-unused-vars
let formData = {};

// eslint-disable-next-line no-unused-vars
const uischema = {
  type: "VerticalLayout",
  elements: [
    {
      type: "Control",
      scope: "#/properties/project_name",
      label: "Project name",
    },
    {
      type: "Control",
      scope: "#/properties/kvk_api_key",
      label: "KvK API key",
    },
    {
      type: "Control",
      scope: "#/properties/business_parks",
      options: {
        multi: true,
      },
    },
  ],
};

const { goToNextStep } = useWorkflow();

const isLoading = ref(true);
const schema = ref({});
const getJsonForm = async () => {
  const request_params = {};
  request_params["url"] = workflowStep.url;
  const queryString = new URLSearchParams(request_params).toString();

  try {
    schema.value = await workflowGetJsonForm(queryString, "CreateProjectSchema");
  } finally {
    isLoading.value = false;
  }
}
getJsonForm();

// eslint-disable-next-line no-unused-vars
const onChange = (event) => {
  formData = event.data;
};

// eslint-disable-next-line no-unused-vars
const onSubmit = async () => {
  const neededKeys = ["kvk_api_key", "project_name", "business_parks"];
  const hasAllKeys = neededKeys.every((key) =>
      Object.keys(formData).includes(key) && Boolean(formData[key])
  );
  if (!hasAllKeys) {
    Swal.fire({
      title: "Oops!",
      text: "Please fill in all required fields.",
      icon: "warning",
      confirmButtonText: "OK",
    });
    return;
  }

  const response = await workflowPostData(workflowStep.url, formData);
  if (response != null) {
    if (response.ok) {
      await Swal.fire({
        title: "EPS project created!",
        text: "An EPS project is created and a project file is being generated. Please wait about 10 minutes. When complete, the file can be downloaded and adjusted under 'Adjust EPS input' and selected as input for 'Run EPS'.",
        icon: "success",
        confirmButtonText: "OK",
      });
      goToNextStep();
    } else {
      const jsonResponse = await response.json();
      let message = "An error occurred when creating the EPS project. Please try again later. Please contact us if the problem persists.";
      if (jsonResponse.message) {
        message = jsonResponse.message;
      }
      await Swal.fire({
        title: "Error",
        text: message,
        icon: "error",
        confirmButtonText: "OK",
      });
    }
  }
};
</script>

<style scoped>
.vertical-layout-item {
  padding-bottom: 5px;
}

.array-list-label {
  font-size: 1rem;
}

.array-list-no-data {
  background-color: rgb(238, 238, 238) !important;
}
</style>