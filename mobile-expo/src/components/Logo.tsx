import { Image, StyleSheet } from 'react-native';

const logoSource = require('../../assets/logo-ifg.png');

export function Logo() {
  return (
    <Image
      source={logoSource}
      style={styles.image}
      resizeMode="contain"
      accessibilityLabel="Imperium Faktur G"
    />
  );
}

const LOGO_SIZE = 61;

const styles = StyleSheet.create({
  image: { width: LOGO_SIZE, height: LOGO_SIZE },
});
