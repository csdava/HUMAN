---
name: Tong Shi Zhi Quan Design System
colors:
  surface: '#f8f9ff'
  surface-dim: '#ccdbf3'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d5e3fc'
  on-surface: '#0d1c2e'
  on-surface-variant: '#434655'
  inverse-surface: '#233144'
  inverse-on-surface: '#eaf1ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#784b00'
  on-tertiary: '#ffffff'
  tertiary-container: '#996100'
  on-tertiary-container: '#ffeedd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#f8f9ff'
  on-background: '#0d1c2e'
  surface-variant: '#d5e3fc'
typography:
  display-lg:
    fontFamily: Manrope
    fontSize: 48px
    fontWeight: '800'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.3'
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.3'
  title-md:
    fontFamily: Manrope
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.05em
  data-numeral:
    fontFamily: IBM Plex Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: -0.01em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  gutter: 20px
  container-max: 1280px
---

## Brand & Style

The design system is anchored in the intersection of cutting-edge edge-computing and the sensitive nature of child nutrition. The brand personality is **authoritative yet approachable**, striking a balance between a sterile medical interface and a friendly educational tool.

The style follows a **Modern Corporate** direction with high-clarity data visualization. It utilizes significant whitespace to convey a sense of "cleanliness" and "safety," essential for health-related software. To avoid appearing overly cold, we incorporate subtle organic curves and high-vibrancy accents that signify vitality and growth. The interface must feel instantaneous—reflecting the speed of edge computing—and hyper-organized, ensuring that parents, teachers, and administrators can find critical nutritional data without friction.

## Colors

The color palette is strategically split into three functional pillars:
- **Edu-Tech Blue (Primary):** Represents intelligence, the edge-computing backend, and institutional trust. Used for primary navigation, school-level actions, and core branding.
- **Vitality Green (Secondary):** Represents health, nutrition, and growth. Used for positive health metrics, dietary balance indicators, and parent-facing wellness summaries.
- **Sunlight Orange (Tertiary):** An accent color for child-centric elements, alerts that require attention but aren't critical errors, and interactive highlights.

**Neutral Scales** utilize a slate-blue tint to maintain a "tech-forward" feel even in gray-scale elements. The background is a very light off-white (`#F8FAFC`) to reduce eye strain during long periods of data entry or report reading.

## Typography

This design system employs a multi-font strategy to differentiate intent:
- **Manrope** is used for headlines and titles. Its modern, geometric yet slightly rounded terminals feel contemporary and friendly.
- **Inter** handles all body copy and prose. Its high x-height and exceptional legibility make it ideal for reading nutritional labels and health reports.
- **IBM Plex Sans** is reserved for data displays, labels, and technical readouts. Its more structured, technical appearance reinforces the "edge-computing" aspect and ensures numerical data is unambiguous.

Large display sizes use tighter letter spacing for a more "designed" look, while labels use expanded tracking to ensure clarity at small scales.

## Layout & Spacing

The layout utilizes a **12-column fluid grid** for desktop and tablet, and a **4-column grid** for mobile. 
- **Desktop:** 24px margins with 20px gutters.
- **Tablet:** 16px margins with 16px gutters.
- **Mobile:** 16px margins with 12px gutters.

The "Card-Based" philosophy dictates that all related data is encapsulated in containers. These containers should follow an 8px-based spacing rhythm for internal padding. To separate the Student, Parent, and School views, the design system uses "Contextual Headers": School views use a sidebar navigation, while Parent/Student views utilize a simplified bottom navigation or top-tab structure to reduce complexity.

## Elevation & Depth

To maintain a clean and professional look, this design system avoids heavy drop shadows. Instead, it uses **Tonal Layers and Soft Ambient Shadows**:

1.  **Level 0 (Background):** `#F8FAFC` - The canvas.
2.  **Level 1 (Cards/Base Surfaces):** White background with a subtle `1px` border in `#E2E8F0`. This creates a crisp, architectural feel.
3.  **Level 2 (Interactive/Floating):** A very soft, diffused shadow (Blur: 15px, Y: 4px, Color: `rgba(37, 99, 235, 0.05)`). The blue tint in the shadow keeps the "Edu-Tech" brand present even in the depth.
4.  **Level 3 (Modals/Overlays):** Stronger diffusion with a backdrop blur (12px) to focus the user's attention on critical health alerts or data entry.

Depth is used to signify "interactivity"—elements that can be tapped or clicked should feel slightly elevated above the static data cards.

## Shapes

The design system uses a **Rounded** shape language (`0.5rem` or `8px` base) to project a "caring" and "safe" image suitable for the education sector. 
- **Standard Components:** Buttons and Input fields use the 8px radius.
- **Data Cards:** Larger containers use `rounded-lg` (16px) to feel more like distinct modules.
- **Status Tags/Chips:** Use `rounded-full` (Pill-shaped) to distinguish them from interactive buttons.

This consistent rounding softens the technical nature of the AI data and makes the system feel more approachable for parents and younger students.

## Components

### Buttons
- **Primary:** Solid "Edu-Tech Blue" with white text. High contrast, 8px corner radius.
- **Secondary:** Ghost style with "Vitality Green" borders and text. Used for secondary health-related actions.
- **Icon Buttons:** Circular or slightly rounded squares for compact toolbars.

### Data Visualization & Cards
- **Nutrition Summary Card:** White background, 16px radius, featuring a "Vitality Green" progress bar for daily intake.
- **AI Insight Chip:** A small, vibrant blue or orange label used to highlight "Edge-AI" generated suggestions (e.g., "Low Sugar Suggestion").

### Input Fields
- **Search & Filter:** Minimalist design with a light gray border. Focus state uses a 2px "Edu-Tech Blue" ring.
- **Health Log Inputs:** Large, easy-to-tap areas for parents to input dietary restrictions or allergies.

### Feedback & Status
- **Health Indicators:** A system of icons (e.g., Heart, Apple, Shield) paired with green/yellow/red status colors to provide immediate visual feedback on a student's nutritional status.
- **Sync Status:** A small, animated pulse icon in the top bar to show real-time edge-computing connectivity.

### Navigation
- **School Dashboard:** Sidebar with high-contrast active states.
- **Parent App:** Bottom navigation with friendly icons and clear labels using **Inter** at 12px.